//! Common process signals and watch-based graceful shutdown mechanics.
//! Callers retain responsibility for draining, health transitions and task completion.

use tokio::sync::watch;

/// A closed sender also ends graceful shutdown, matching existing service loops.
pub async fn wait_for_shutdown(shutdown: &mut watch::Receiver<bool>) {
    while !*shutdown.borrow() && shutdown.changed().await.is_ok() {}
}

/// Match services that fail startup if installing a signal handler fails.
pub async fn shutdown_signal() {
    signal(false).await;
}

/// Match services whose existing policy returns on signal installation errors.
pub async fn shutdown_signal_best_effort() {
    signal(true).await;
}

async fn signal(best_effort: bool) {
    let ctrl_c = async {
        let result = tokio::signal::ctrl_c().await;
        if !best_effort {
            result.expect("failed to install Ctrl+C handler");
        }
    };
    #[cfg(unix)]
    let terminate = async {
        let result = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate());
        if best_effort {
            if let Ok(mut signal) = result {
                signal.recv().await;
            }
        } else {
            result
                .expect("failed to install SIGTERM handler")
                .recv()
                .await;
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! { () = ctrl_c => {}, () = terminate => {} }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn waits_through_false_then_releases_all_receivers_on_true() {
        let (tx, mut first) = watch::channel(false);
        let mut second = first.clone();
        assert!(
            tokio::time::timeout(Duration::from_millis(10), wait_for_shutdown(&mut first))
                .await
                .is_err()
        );
        tx.send(false).unwrap();
        assert!(
            tokio::time::timeout(Duration::from_millis(10), wait_for_shutdown(&mut first))
                .await
                .is_err()
        );
        tx.send(true).unwrap();
        tokio::time::timeout(Duration::from_secs(1), async {
            tokio::join!(
                wait_for_shutdown(&mut first),
                wait_for_shutdown(&mut second)
            );
        })
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn already_requested_shutdown_returns_without_another_notification() {
        let (_tx, mut rx) = watch::channel(true);
        tokio::time::timeout(Duration::from_secs(1), wait_for_shutdown(&mut rx))
            .await
            .unwrap();
    }

    #[tokio::test]
    async fn closed_sender_releases_a_waiting_receiver() {
        let (tx, mut rx) = watch::channel(false);
        tokio::time::timeout(Duration::from_secs(1), async {
            tokio::join!(wait_for_shutdown(&mut rx), async {
                tokio::task::yield_now().await;
                drop(tx);
            });
        })
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn already_closed_sender_returns_without_a_true_value() {
        let (tx, mut rx) = watch::channel(false);
        drop(tx);
        tokio::time::timeout(Duration::from_secs(1), wait_for_shutdown(&mut rx))
            .await
            .unwrap();
    }
}
