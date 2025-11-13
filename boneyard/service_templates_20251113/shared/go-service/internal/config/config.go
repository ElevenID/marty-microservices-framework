package config

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	Environment string
	Port        string
	LogLevel    string
	ServiceName string

	{{- if include_database }}
	// Database configuration
	DatabaseURL      string
	DatabaseHost     string
	DatabasePort     string
	DatabaseUser     string
	DatabasePassword string
	DatabaseName     string
	DatabaseSSLMode  string
	{{- endif }}

	{{- if include_redis }}
	// Redis configuration
	RedisURL      string
	RedisHost     string
	RedisPort     string
	RedisPassword string
	RedisDB       int
	{{- endif }}

	{{- if include_auth }}
	// JWT configuration
	JWTSecret     string
	JWTExpiresIn  string
	{{- endif }}

	// Security
	CORSOrigins []string
	RateLimit   int

	// Monitoring
	MetricsPath string
	HealthPath  string
}

func Load() (*Config, error) {
	// Load .env file if it exists
	_ = godotenv.Load()

	cfg := &Config{
		Environment: getEnv("ENVIRONMENT", "development"),
		Port:        getEnv("PORT", "{{ port }}"),
		LogLevel:    getEnv("LOG_LEVEL", "info"),
		ServiceName: getEnv("SERVICE_NAME", "{{ service_name }}"),

		{{- if include_database }}
		DatabaseURL:      getEnv("DATABASE_URL", ""),
		DatabaseHost:     getEnv("DATABASE_HOST", "localhost"),
		DatabasePort:     getEnv("DATABASE_PORT", "5432"),
		DatabaseUser:     getEnv("DATABASE_USER", "postgres"),
		DatabasePassword: getEnv("DATABASE_PASSWORD", "password"),
		DatabaseName:     getEnv("DATABASE_NAME", ""),
		DatabaseSSLMode:  getEnv("DATABASE_SSL_MODE", "disable"),
		{{- endif }}

		{{- if include_redis }}
		RedisURL:      getEnv("REDIS_URL", ""),
		RedisHost:     getEnv("REDIS_HOST", "localhost"),
		RedisPort:     getEnv("REDIS_PORT", "6379"),
		RedisPassword: getEnv("REDIS_PASSWORD", ""),
		RedisDB:       getEnvAsInt("REDIS_DB", 0),
		{{- endif }}

		{{- if include_auth }}
		JWTSecret:    getEnv("JWT_SECRET", "your-secret-key"),
		JWTExpiresIn: getEnv("JWT_EXPIRES_IN", "24h"),
		{{- endif }}

		CORSOrigins: []string{getEnv("CORS_ORIGINS", "*")},
		RateLimit:   getEnvAsInt("RATE_LIMIT", 100),

		MetricsPath: getEnv("METRICS_PATH", "/metrics"),
		HealthPath:  getEnv("HEALTH_PATH", "/health"),
	}

	return cfg, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(name string, defaultValue int) int {
	valueStr := getEnv(name, "")
	if value, err := strconv.Atoi(valueStr); err == nil {
		return value
	}
	return defaultValue
}
