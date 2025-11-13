package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"{{ module_name }}/internal/app"
	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Initialize logger
	logger := logger.NewLogger(cfg.LogLevel)

	// Create application
	application, err := app.NewApp(cfg, logger)
	if err != nil {
		logger.Fatalf("Failed to create application: %v", err)
	}

	// Start server
	server := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      application.Router,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	go func() {
		logger.Infof("Starting {{ service_name }} on port %s", cfg.Port)
		logger.Infof("Environment: %s", cfg.Environment)
		logger.Infof("Log Level: %s", cfg.LogLevel)

		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatalf("Server failed to start: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("Shutting down server...")

	// Create shutdown context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Shutdown application
	if err := application.Shutdown(ctx); err != nil {
		logger.Errorf("Application shutdown error: %v", err)
	}

	// Shutdown server
	if err := server.Shutdown(ctx); err != nil {
		logger.Errorf("Server shutdown error: %v", err)
	}

	logger.Info("Server shutdown complete")
}
