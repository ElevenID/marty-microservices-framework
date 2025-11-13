import app from './app';
import { logger } from './config/logger';
import { config } from './config/config';
{% if include_database %}import { DatabaseManager } from './database/manager';{% endif %}
{% if include_redis %}import { initializeRedis } from './config/redis';{% endif %}

/**
 * Server startup and graceful shutdown handling
 */

const PORT = config.port || {{ port }};
let server: any;
{% if include_database %}let dbManager: DatabaseManager;{% endif %}

async function startServer() {
  try {
    {% if include_database %}// Initialize database connection using Marty framework pattern
    dbManager = DatabaseManager.getInstance(config.serviceName);
    await dbManager.initialize();
    logger.info('Database connection established using Marty framework');{% endif %}

    {% if include_redis %}// Initialize Redis connection
    await initializeRedis();
    logger.info('Redis connection established');{% endif %}

    // Start HTTP server
    server = app.listen(PORT, () => {
      logger.info(`🚀 {{ service_name }} is running on port ${PORT}`);
      logger.info(`📖 API Documentation: http://localhost:${PORT}/docs`);
      logger.info(`❤️  Health Check: http://localhost:${PORT}/health`);
      logger.info(`📊 Metrics: http://localhost:${PORT}/metrics`);
    });

    // Handle server errors
    server.on('error', (error: any) => {
      if (error.syscall !== 'listen') {
        throw error;
      }

      const bind = typeof PORT === 'string' ? `Pipe ${PORT}` : `Port ${PORT}`;

      switch (error.code) {
        case 'EACCES':
          logger.error(`${bind} requires elevated privileges`);
          process.exit(1);
          break;
        case 'EADDRINUSE':
          logger.error(`${bind} is already in use`);
          process.exit(1);
          break;
        default:
          throw error;
      }
    });

  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Graceful shutdown handling
async function gracefulShutdown(signal: string) {
  logger.info(`Received ${signal}. Starting graceful shutdown...`);

  if (server) {
    server.close(async () => {
      logger.info('HTTP server closed');

      try {
        {% if include_database %}// Close database connections using Marty framework
        if (dbManager) {
          await dbManager.close();
          logger.info('Database connections closed');
        }{% endif %}

        {% if include_redis %}// Close Redis connection
        const { redis } = require('./config/redis');
        if (redis) {
          await redis.quit();
          logger.info('Redis connection closed');
        }{% endif %}

        logger.info('Graceful shutdown completed');
        process.exit(0);
      } catch (error) {
        logger.error('Error during graceful shutdown:', error);
        process.exit(1);
      }
    });

    // Force close after 30 seconds
    setTimeout(() => {
      logger.error('Could not close connections in time, forcefully shutting down');
      process.exit(1);
    }, 30000);
  } else {
    process.exit(0);
  }
}

// Handle shutdown signals
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error);
  gracefulShutdown('uncaughtException');
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
  gracefulShutdown('unhandledRejection');
});

// Start the server
startServer();
