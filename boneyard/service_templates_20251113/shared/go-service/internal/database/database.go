package database

import (
	"fmt"
	"sync"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"{{ module_name }}/internal/config"
	applogger "{{ module_name }}/internal/logger"
)

// DatabaseManager implements Marty framework database patterns
type DatabaseManager struct {
	db     *gorm.DB
	logger applogger.Logger
	config *config.Config
	mu     sync.RWMutex
}

var (
	instance *DatabaseManager
	once     sync.Once
)

// GetInstance returns singleton database manager for service
func GetInstance(serviceName string, cfg *config.Config, log applogger.Logger) (*DatabaseManager, error) {
	var err error

	once.Do(func() {
		instance = &DatabaseManager{
			logger: log,
			config: cfg,
		}
		err = instance.initialize()
	})

	if err != nil {
		return nil, err
	}

	return instance, nil
}

// initialize sets up the database connection following Marty patterns
func (m *DatabaseManager) initialize() error {
	// Build service-specific database name following Marty conventions
	serviceName := m.config.ServiceName
	if serviceName == "" {
		serviceName = "{{ service_name }}"
	}

	var dsn string
	if m.config.DatabaseURL != "" {
		dsn = m.config.DatabaseURL
	} else {
		// Use service-specific database name
		dbName := m.config.DatabaseName
		if dbName == "" {
			// Generate service-specific database name
			dbName = fmt.Sprintf("%s_db", serviceName)
		}

		dsn = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
			m.config.DatabaseHost,
			m.config.DatabasePort,
			m.config.DatabaseUser,
			m.config.DatabasePassword,
			dbName,
			m.config.DatabaseSSLMode,
		)
	}

	// Configure GORM logger
	var gormLogger logger.Interface
	if m.config.LogLevel == "debug" {
		gormLogger = logger.Default.LogMode(logger.Info)
	} else {
		gormLogger = logger.Default.LogMode(logger.Silent)
	}

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: gormLogger,
	})
	if err != nil {
		return fmt.Errorf("failed to connect to database for service %s: %w", serviceName, err)
	}

	// Test connection
	sqlDB, err := db.DB()
	if err != nil {
		return fmt.Errorf("failed to get database instance: %w", err)
	}

	if err := sqlDB.Ping(); err != nil {
		return fmt.Errorf("failed to ping database: %w", err)
	}

	// Configure connection pool
	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)

	m.db = db

	m.logger.Info("Database manager initialized for service", "service", serviceName)
	return nil
}
func (m *DatabaseManager) DB() *gorm.DB {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.db
}

func (m *DatabaseManager) Ping() error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.db == nil {
		return fmt.Errorf("database not initialized")
	}

	sqlDB, err := m.db.DB()
	if err != nil {
		return err
	}
	return sqlDB.Ping()
}

func (m *DatabaseManager) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.db == nil {
		return nil
	}

	sqlDB, err := m.db.DB()
	if err != nil {
		return err
	}

	if err := sqlDB.Close(); err != nil {
		return err
	}

	m.db = nil
	m.logger.Info("Database manager closed")
	return nil
}

// HealthCheck performs database health check following Marty patterns
func (m *DatabaseManager) HealthCheck() (map[string]interface{}, error) {
	if err := m.Ping(); err != nil {
		return map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}, err
	}

	sqlDB, err := m.db.DB()
	if err != nil {
		return map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}, err
	}

	stats := sqlDB.Stats()
	return map[string]interface{}{
		"status":         "healthy",
		"open_connections": stats.OpenConnections,
		"in_use":         stats.InUse,
		"idle":           stats.Idle,
	}, nil
}

// AutoMigrate runs database migrations
func (m *DatabaseManager) AutoMigrate(models ...interface{}) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.db == nil {
		return fmt.Errorf("database not initialized")
	}

	return m.db.AutoMigrate(models...)
}

// CloseAll closes all database manager instances
func CloseAll() error {
	mu.Lock()
	defer mu.Unlock()

	var lastErr error
	for serviceName, manager := range instances {
		if err := manager.Close(); err != nil {
			lastErr = err
		}
		delete(instances, serviceName)
	}

	return lastErr
}
