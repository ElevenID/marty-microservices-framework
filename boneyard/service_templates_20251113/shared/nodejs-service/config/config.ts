import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

export const config = {
  // Server
  port: parseInt(process.env.PORT || '{{ port }}', 10),
  nodeEnv: process.env.NODE_ENV || 'development',

  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',

  // Database{% if include_database %}
  database: {
    url: process.env.DATABASE_URL || 'postgresql://user:password@localhost:5432/{{ service_name }}',
    pool: {
      min: parseInt(process.env.DB_POOL_MIN || '2', 10),
      max: parseInt(process.env.DB_POOL_MAX || '10', 10),
    },
  },{% endif %}

  // Redis{% if include_redis %}
  redis: {
    url: process.env.REDIS_URL || 'redis://localhost:6379',
    retryDelayOnFailover: 100,
    enableReadyCheck: false,
    maxRetriesPerRequest: null,
  },{% endif %}

  // Authentication{% if include_auth %}
  jwt: {
    secret: process.env.JWT_SECRET || 'your-super-secret-jwt-key',
    expiresIn: process.env.JWT_EXPIRES_IN || '24h',
  },{% endif %}

  // Security
  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000', 10), // 15 minutes
    max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100', 10),
  },

  // CORS
  cors: {
    origin: process.env.CORS_ORIGIN ? process.env.CORS_ORIGIN.split(',') : ['http://localhost:3000'],
    credentials: true,
  },
};
