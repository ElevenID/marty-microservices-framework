package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"

	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
	{{- if include_database }}
	"{{ module_name }}/internal/database"
	{{- endif }}
	{{- if include_redis }}
	"{{ module_name }}/internal/redis"
	{{- endif }}
)

type HealthResponse struct {
	Status    string                 `json:"status"`
	Timestamp time.Time              `json:"timestamp"`
	Service   string                 `json:"service"`
	Version   string                 `json:"version"`
	Checks    map[string]interface{} `json:"checks"`
}

// HealthCheck returns the health status of the service
func HealthCheck(cfg *config.Config, log logger.Logger{{- if include_database }}, dbManager *database.DatabaseManager{{- endif }}{{- if include_redis }}, redis *redis.Client{{- endif }}) gin.HandlerFunc {
	return func(c *gin.Context) {
		checks := make(map[string]interface{})
		healthy := true

		{{- if include_database }}
		// Check database connection
		if dbManager != nil {
			if err := dbManager.HealthCheck(); err != nil {
				checks["database"] = map[string]interface{}{
					"status": "unhealthy",
					"error":  err.Error(),
				}
				healthy = false
			} else {
				checks["database"] = map[string]interface{}{
					"status": "healthy",
				}
			}
		}
		{{- endif }}

		{{- if include_redis }}
		// Check Redis connection
		if redis != nil {
			if err := redis.Ping(); err != nil {
				checks["redis"] = map[string]interface{}{
					"status": "unhealthy",
					"error":  err.Error(),
				}
				healthy = false
			} else {
				checks["redis"] = map[string]interface{}{
					"status": "healthy",
				}
			}
		}
		{{- endif }}

		status := "healthy"
		statusCode := http.StatusOK
		if !healthy {
			status = "unhealthy"
			statusCode = http.StatusServiceUnavailable
		}

		response := HealthResponse{
			Status:    status,
			Timestamp: time.Now(),
			Service:   "{{ service_name }}",
			Version:   "1.0.0",
			Checks:    checks,
		}

		c.JSON(statusCode, response)
	}
}

// Root handler
func Root(log logger.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "Welcome to {{ service_name }}",
			"service": "{{ service_name }}",
			"version": "1.0.0",
		})
	}
}

// Ping handler
func Ping(log logger.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "pong",
			"timestamp": time.Now(),
		})
	}
}
