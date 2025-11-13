package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"

	"{{ module_name }}/internal/config"
	"{{ module_name }}/internal/logger"
)

type Client struct {
	client *redis.Client
	logger logger.Logger
}

func NewClient(cfg *config.Config, log logger.Logger) (*Client, error) {
	var addr string

	if cfg.RedisURL != "" {
		opts, err := redis.ParseURL(cfg.RedisURL)
		if err != nil {
			return nil, fmt.Errorf("failed to parse Redis URL: %w", err)
		}

		client := redis.NewClient(opts)

		// Test connection
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		if err := client.Ping(ctx).Err(); err != nil {
			return nil, fmt.Errorf("failed to ping Redis: %w", err)
		}

		log.Info("Connected to Redis successfully")

		return &Client{
			client: client,
			logger: log,
		}, nil
	}

	addr = fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort)

	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to ping Redis: %w", err)
	}

	log.Info("Connected to Redis successfully")

	return &Client{
		client: client,
		logger: log,
	}, nil
}

func (c *Client) Client() *redis.Client {
	return c.client
}

func (c *Client) Ping() error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return c.client.Ping(ctx).Err()
}

func (c *Client) Close() error {
	return c.client.Close()
}

// Set stores a key-value pair with expiration
func (c *Client) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	return c.client.Set(ctx, key, value, expiration).Err()
}

// Get retrieves a value by key
func (c *Client) Get(ctx context.Context, key string) (string, error) {
	return c.client.Get(ctx, key).Result()
}

// Del deletes keys
func (c *Client) Del(ctx context.Context, keys ...string) error {
	return c.client.Del(ctx, keys...).Err()
}

// Exists checks if keys exist
func (c *Client) Exists(ctx context.Context, keys ...string) (int64, error) {
	return c.client.Exists(ctx, keys...).Result()
}

// Expire sets expiration for a key
func (c *Client) Expire(ctx context.Context, key string, expiration time.Duration) error {
	return c.client.Expire(ctx, key, expiration).Err()
}
