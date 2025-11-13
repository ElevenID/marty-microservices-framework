package app

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
	"{{ module_name }}/internal/middleware"
	"{{ module_name }}/internal/handlers"
	{{- if include_database }}
	"{{ module_name }}/internal/database"
	{{- endif }}
	{{- if include_redis }}
	"{{ module_name }}/internal/redis"
	{{- endif }}
)

type App struct {
	config    *config.Config
	logger    logger.Logger
	Router    *gin.Engine
	{{- if include_database }}
	dbManager *database.DatabaseManager
	{{- endif }}
	{{- if include_redis }}
	redis     *redis.Client
	{{- endif }}
}

func NewApp(cfg *config.Config, log logger.Logger) (*App, error) {
	app := &App{
		config: cfg,
		logger: log,
	}

	// Set Gin mode
	if cfg.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Initialize router
	app.Router = gin.New()

	{{- if include_database }}
	// Initialize database using Marty framework patterns
	dbManager, err := database.GetInstance(cfg.ServiceName, cfg, log)
	if err != nil {
		return nil, err
	}
	app.dbManager = dbManager
	{{- endif }}

	{{- if include_redis }}
	// Initialize Redis
	redis, err := redis.NewClient(cfg, log)
	if err != nil {
		return nil, err
	}
	app.redis = redis
	{{- endif }}

	// Setup middleware
	app.setupMiddleware()

	// Setup routes
	app.setupRoutes()

	return app, nil
}

func (a *App) setupMiddleware() {
	// Recovery middleware
	a.Router.Use(gin.Recovery())

	// Logger middleware
	a.Router.Use(middleware.Logger(a.logger))

	// CORS middleware
	a.Router.Use(middleware.CORS(a.config.CORSOrigins))

	// Rate limiter middleware
	a.Router.Use(middleware.RateLimit(a.config.RateLimit))

	// Security headers middleware
	a.Router.Use(middleware.Security())

	// Request ID middleware
	a.Router.Use(middleware.RequestID())

	// Prometheus metrics middleware
	a.Router.Use(middleware.Metrics())
}

func (a *App) setupRoutes() {
	// Health check
	a.Router.GET(a.config.HealthPath, handlers.HealthCheck(a.config, a.logger{{- if include_database }}, a.dbManager{{- endif }}{{- if include_redis }}, a.redis{{- endif }}))

	// Metrics endpoint
	a.Router.GET(a.config.MetricsPath, gin.WrapH(promhttp.Handler()))

	// API routes
	api := a.Router.Group("/api/v1")
	{
		{{- if include_auth }}
		// Auth routes
		auth := api.Group("/auth")
		{
			auth.POST("/login", handlers.Login(a.config, a.logger{{- if include_database }}, a.dbManager{{- endif }}))
			auth.POST("/register", handlers.Register(a.config, a.logger{{- if include_database }}, a.dbManager{{- endif }}))
			auth.POST("/refresh", handlers.RefreshToken(a.config, a.logger{{- if include_database }}, a.dbManager{{- endif }}))
		}

		// Protected routes
		protected := api.Group("/")
		protected.Use(middleware.AuthMiddleware(a.config.JWTSecret))
		{
			protected.GET("/profile", handlers.GetProfile(a.logger{{- if include_database }}, a.dbManager{{- endif }}))
		}
		{{- endif }}

		// Example routes
		api.GET("/", handlers.Root(a.logger))
		api.GET("/ping", handlers.Ping(a.logger))
	}
}

func (a *App) Shutdown(ctx context.Context) error {
	a.logger.Info("Shutting down application...")

	{{- if include_database }}
	// Close database connection
	if a.dbManager != nil {
		if err := a.dbManager.Close(); err != nil {
			a.logger.Errorf("Error closing database: %v", err)
		}
	}
	{{- endif }}

	{{- if include_redis }}
	// Close Redis connection
	if a.redis != nil {
		if err := a.redis.Close(); err != nil {
			a.logger.Errorf("Error closing Redis: %v", err)
		}
	}
	{{- endif }}

	return nil
}
