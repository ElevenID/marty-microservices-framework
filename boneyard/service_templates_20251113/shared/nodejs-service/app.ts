import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import compression from 'compression';
import rateLimit from 'express-rate-limit';
import { createPrometheusMetrics } from './middleware/metrics';
import { errorHandler } from './middleware/errorHandler';
import { requestLogger } from './middleware/logger';
import { healthRoutes } from './routes/health';
import { apiRoutes } from './routes/api';
{% if include_auth %}import { authRoutes } from './routes/auth';{% endif %}
import { swaggerSpec, swaggerUi } from './config/swagger';
import { logger } from './config/logger';
import { config } from './config/config';

/**
 * {{ service_description }}
 *
 * Enterprise-grade Node.js microservice with:
 * - Express.js framework with TypeScript
 * - Comprehensive security middleware
 * - Prometheus metrics and monitoring
 * - Structured logging with Winston
 * - JWT authentication{% if include_auth %} (enabled){% else %} (disabled){% endif %}
 * - Database integration{% if include_database %} (PostgreSQL enabled){% else %} (disabled){% endif %}
 * - Redis caching{% if include_redis %} (enabled){% else %} (disabled){% endif %}
 * - API documentation with Swagger
 * - Health checks and graceful shutdown
 * - Docker containerization
 * - Comprehensive test suite
 */

const app = express();

// Initialize Prometheus metrics
const { requestDuration, requestCount, errorCount } = createPrometheusMetrics();

// Security middleware
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", "data:", "https:"],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true
  }
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.',
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

// Basic middleware
app.use(cors());
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Request logging
app.use(morgan('combined'));
app.use(requestLogger);

// Metrics middleware
app.use((req, res, next) => {
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    const route = req.route?.path || req.path;
    const method = req.method;
    const status = res.statusCode;

    requestDuration
      .labels(method, route, status.toString())
      .observe(duration / 1000);

    requestCount
      .labels(method, route, status.toString())
      .inc();

    if (status >= 400) {
      errorCount
        .labels(method, route, status.toString())
        .inc();
    }
  });

  next();
});

// API Documentation
app.use('/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));

// Routes
app.use('/health', healthRoutes);
app.use('/api', apiRoutes);
{% if include_auth %}app.use('/auth', authRoutes);{% endif %}

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    service: '{{ service_name }}',
    description: '{{ service_description }}',
    version: '1.0.0',
    status: 'running',
    timestamp: new Date().toISOString(),
    documentation: '/docs',
    health: '/health',
    metrics: '/metrics'
  });
});

// Metrics endpoint for Prometheus
app.get('/metrics', async (req, res) => {
  try {
    const register = require('prom-client').register;
    const metrics = await register.metrics();
    res.set('Content-Type', register.contentType);
    res.end(metrics);
  } catch (error) {
    res.status(500).json({ error: 'Failed to generate metrics' });
  }
});

// Error handling middleware (must be last)
app.use(errorHandler);

// Handle 404
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Not Found',
    message: `Route ${req.originalUrl} not found`,
    timestamp: new Date().toISOString()
  });
});

export default app;
