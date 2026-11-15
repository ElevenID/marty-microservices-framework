use std::any::{Any, TypeId, type_name};
use std::collections::{BTreeMap, btree_map::Entry};
use std::sync::{Arc, Mutex, RwLock};

use mmf_core::{ErrorCode, MmfError};
use serde_json::Value;

type Service = Arc<dyn Any + Send + Sync>;
type Factory = Arc<dyn Fn(&Value) -> Result<Service, MmfError> + Send + Sync>;
type Shutdown = Arc<dyn Fn(Service) -> Result<(), MmfError> + Send + Sync>;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ServiceLifetime {
    Singleton,
    Scoped,
    Transient,
}

struct Registration {
    service_name: &'static str,
    lifetime: ServiceLifetime,
    config: Value,
    factory: Factory,
    shutdown: Option<Shutdown>,
    singleton: Mutex<Option<Service>>,
}

#[derive(Clone, Default)]
pub struct ServiceContainer {
    registrations: Arc<RwLock<BTreeMap<TypeId, Arc<Registration>>>>,
}

impl ServiceContainer {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register_instance<T>(&self, instance: Arc<T>) -> Result<(), MmfError>
    where
        T: Any + Send + Sync,
    {
        let service: Service = instance;
        self.insert::<T>(Registration {
            service_name: type_name::<T>(),
            lifetime: ServiceLifetime::Singleton,
            config: Value::Object(serde_json::Map::new()),
            factory: Arc::new(|_| {
                Err(MmfError::new(
                    ErrorCode::Internal,
                    "instance factory must not be called",
                ))
            }),
            shutdown: None,
            singleton: Mutex::new(Some(service)),
        })
    }

    pub fn register<T, F>(
        &self,
        lifetime: ServiceLifetime,
        config: Value,
        factory: F,
    ) -> Result<(), MmfError>
    where
        T: Any + Send + Sync,
        F: Fn(&Value) -> Result<T, MmfError> + Send + Sync + 'static,
    {
        self.register_with_shutdown(
            lifetime,
            config,
            factory,
            None::<fn(Arc<T>) -> Result<(), MmfError>>,
        )
    }

    pub fn register_with_shutdown<T, F, S>(
        &self,
        lifetime: ServiceLifetime,
        config: Value,
        factory: F,
        shutdown: Option<S>,
    ) -> Result<(), MmfError>
    where
        T: Any + Send + Sync,
        F: Fn(&Value) -> Result<T, MmfError> + Send + Sync + 'static,
        S: Fn(Arc<T>) -> Result<(), MmfError> + Send + Sync + 'static,
    {
        let factory = Arc::new(move |config: &Value| {
            factory(config).map(|service| Arc::new(service) as Service)
        });
        let shutdown = shutdown.map(|shutdown| {
            Arc::new(move |service: Service| {
                Arc::downcast::<T>(service)
                    .map_err(|_| MmfError::new(ErrorCode::Internal, "service type mismatch"))
                    .and_then(&shutdown)
            }) as Shutdown
        });
        self.insert::<T>(Registration {
            service_name: type_name::<T>(),
            lifetime,
            config,
            factory,
            shutdown,
            singleton: Mutex::new(None),
        })
    }

    pub fn resolve<T>(&self) -> Result<Arc<T>, MmfError>
    where
        T: Any + Send + Sync,
    {
        let registration = self.registration::<T>()?;
        if registration.lifetime == ServiceLifetime::Scoped {
            return Err(MmfError::new(
                ErrorCode::Conflict,
                format!(
                    "scoped service {} requires a scope",
                    registration.service_name
                ),
            ));
        }
        resolve_registration::<T>(&registration)
    }

    #[must_use]
    pub fn has<T>(&self) -> bool
    where
        T: Any + Send + Sync,
    {
        self.registrations
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .contains_key(&TypeId::of::<T>())
    }

    pub fn create_scope(&self, name: impl Into<String>) -> Result<ServiceScope, MmfError> {
        let name = name.into();
        if name.trim().is_empty() {
            return Err(MmfError::new(
                ErrorCode::InvalidInput,
                "scope name is required",
            ));
        }
        Ok(ServiceScope {
            name,
            container: self.clone(),
            services: Mutex::new(BTreeMap::new()),
        })
    }

    pub fn shutdown(&self) -> Result<(), MmfError> {
        let registrations = self
            .registrations
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "service registry lock poisoned"))?;
        let mut first_error = None;
        for registration in registrations.values() {
            let service = registration
                .singleton
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .take();
            if let (Some(service), Some(shutdown)) = (service, &registration.shutdown)
                && let Err(error) = shutdown(service)
                && first_error.is_none()
            {
                first_error = Some(error);
            }
        }
        first_error.map_or(Ok(()), Err)
    }

    fn insert<T>(&self, registration: Registration) -> Result<(), MmfError>
    where
        T: Any + Send + Sync,
    {
        let mut registrations = self
            .registrations
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "service registry lock poisoned"))?;
        match registrations.entry(TypeId::of::<T>()) {
            Entry::Vacant(entry) => {
                entry.insert(Arc::new(registration));
                Ok(())
            }
            Entry::Occupied(_) => Err(MmfError::new(
                ErrorCode::Conflict,
                format!("service {} is already registered", type_name::<T>()),
            )),
        }
    }

    fn registration<T>(&self) -> Result<Arc<Registration>, MmfError>
    where
        T: Any + Send + Sync,
    {
        self.registrations
            .read()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "service registry lock poisoned"))?
            .get(&TypeId::of::<T>())
            .cloned()
            .ok_or_else(|| {
                MmfError::new(
                    ErrorCode::DependencyUnavailable,
                    format!("service {} is not registered", type_name::<T>()),
                )
            })
    }
}

pub struct ServiceScope {
    name: String,
    container: ServiceContainer,
    services: Mutex<BTreeMap<TypeId, Service>>,
}

impl ServiceScope {
    #[must_use]
    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn resolve<T>(&self) -> Result<Arc<T>, MmfError>
    where
        T: Any + Send + Sync,
    {
        let registration = self.container.registration::<T>()?;
        if registration.lifetime != ServiceLifetime::Scoped {
            return resolve_registration::<T>(&registration);
        }
        let mut services = self
            .services
            .lock()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "scope lock poisoned"))?;
        let service = if let Some(service) = services.get(&TypeId::of::<T>()) {
            service.clone()
        } else {
            let service = (registration.factory)(&registration.config)?;
            services.insert(TypeId::of::<T>(), service.clone());
            service
        };
        Arc::downcast::<T>(service)
            .map_err(|_| MmfError::new(ErrorCode::Internal, "service type mismatch"))
    }
}

fn resolve_registration<T>(registration: &Registration) -> Result<Arc<T>, MmfError>
where
    T: Any + Send + Sync,
{
    let service = match registration.lifetime {
        ServiceLifetime::Singleton => {
            let mut singleton = registration
                .singleton
                .lock()
                .map_err(|_| MmfError::new(ErrorCode::Internal, "service lock poisoned"))?;
            if let Some(service) = singleton.as_ref() {
                service.clone()
            } else {
                let service = (registration.factory)(&registration.config)?;
                *singleton = Some(service.clone());
                service
            }
        }
        ServiceLifetime::Transient => (registration.factory)(&registration.config)?,
        ServiceLifetime::Scoped => {
            return Err(MmfError::new(
                ErrorCode::Conflict,
                "scoped service requires a scope",
            ));
        }
    };
    Arc::downcast::<T>(service)
        .map_err(|_| MmfError::new(ErrorCode::Internal, "service type mismatch"))
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicU64, Ordering};

    use serde::Deserialize;
    use serde_json::json;

    use super::*;

    #[derive(Debug)]
    struct Service(u64);

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        lifetimes: LifetimeCase,
    }

    #[derive(Deserialize)]
    #[allow(clippy::struct_excessive_bools)]
    struct LifetimeCase {
        singleton_same: bool,
        transient_same: bool,
        scope_same: bool,
        cross_scope_same: bool,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/config-runtime-behavior.json"
        ))
        .expect("valid config/runtime fixture")
    }

    fn counter_factory(counter: Arc<AtomicU64>) -> impl Fn(&Value) -> Result<Service, MmfError> {
        move |_| Ok(Service(counter.fetch_add(1, Ordering::Relaxed)))
    }

    #[test]
    fn service_lifetimes_match_the_shared_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let counter = Arc::new(AtomicU64::new(1));

        let singleton = ServiceContainer::new();
        singleton
            .register(
                ServiceLifetime::Singleton,
                json!({}),
                counter_factory(counter.clone()),
            )
            .expect("register singleton");
        assert_eq!(
            Arc::ptr_eq(
                &singleton.resolve::<Service>().expect("first"),
                &singleton.resolve::<Service>().expect("second")
            ),
            fixture.lifetimes.singleton_same
        );

        let transient = ServiceContainer::new();
        transient
            .register(
                ServiceLifetime::Transient,
                json!({}),
                counter_factory(counter.clone()),
            )
            .expect("register transient");
        assert_eq!(
            Arc::ptr_eq(
                &transient.resolve::<Service>().expect("first"),
                &transient.resolve::<Service>().expect("second")
            ),
            fixture.lifetimes.transient_same
        );

        let scoped = ServiceContainer::new();
        scoped
            .register(ServiceLifetime::Scoped, json!({}), counter_factory(counter))
            .expect("register scoped");
        assert!(scoped.resolve::<Service>().is_err());
        let first = scoped.create_scope("first").expect("scope");
        let second = scoped.create_scope("second").expect("scope");
        let first_value = first.resolve::<Service>().expect("first");
        assert_eq!(
            Arc::ptr_eq(
                &first_value,
                &first.resolve::<Service>().expect("same scope")
            ),
            fixture.lifetimes.scope_same
        );
        assert_eq!(
            Arc::ptr_eq(
                &first_value,
                &second.resolve::<Service>().expect("other scope")
            ),
            fixture.lifetimes.cross_scope_same
        );
        assert!(first_value.0 > 0);
    }

    #[test]
    fn rejected_duplicate_instance_keeps_the_original_service() {
        let container = ServiceContainer::new();
        let original = Arc::new(Service(7));
        container
            .register_instance(original.clone())
            .expect("register original");

        let error = container
            .register_instance(Arc::new(Service(99)))
            .expect_err("reject duplicate");
        assert_eq!(error.code, ErrorCode::Conflict);
        assert!(Arc::ptr_eq(
            &original,
            &container.resolve::<Service>().expect("original remains")
        ));
    }

    #[test]
    fn rejected_duplicate_factory_keeps_the_original_lifetime() {
        let container = ServiceContainer::new();
        container
            .register(ServiceLifetime::Scoped, json!({}), |_| Ok(Service(7)))
            .expect("register original");
        let error = container
            .register(ServiceLifetime::Singleton, json!({}), |_| Ok(Service(99)))
            .expect_err("reject duplicate");
        assert_eq!(error.code, ErrorCode::Conflict);
        assert_eq!(
            container
                .resolve::<Service>()
                .expect_err("original still requires a scope")
                .code,
            ErrorCode::Conflict
        );
        let scope = container.create_scope("retained").expect("scope");
        assert_eq!(scope.resolve::<Service>().expect("original factory").0, 7);
    }

    #[test]
    fn rejected_duplicate_keeps_the_original_shutdown_callback() {
        let container = ServiceContainer::new();
        let shutdown_value = Arc::new(AtomicU64::new(0));
        let original_shutdown = shutdown_value.clone();
        container
            .register_with_shutdown(
                ServiceLifetime::Singleton,
                json!({}),
                |_| Ok(Service(7)),
                Some(move |service: Arc<Service>| {
                    original_shutdown.fetch_add(service.0, Ordering::Relaxed);
                    Ok(())
                }),
            )
            .expect("register original");
        let original = container
            .resolve::<Service>()
            .expect("instantiate original");
        let duplicate_shutdown = shutdown_value.clone();
        let error = container
            .register_with_shutdown(
                ServiceLifetime::Singleton,
                json!({}),
                |_| Ok(Service(99)),
                Some(move |service: Arc<Service>| {
                    duplicate_shutdown.fetch_add(service.0, Ordering::Relaxed);
                    Ok(())
                }),
            )
            .expect_err("reject duplicate");
        assert_eq!(error.code, ErrorCode::Conflict);
        container.shutdown().expect("shutdown original");
        container.shutdown().expect("shutdown is idempotent");
        assert_eq!(shutdown_value.load(Ordering::Relaxed), original.0);
    }
}
