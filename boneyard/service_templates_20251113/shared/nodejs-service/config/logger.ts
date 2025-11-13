import winston from 'winston';
import { config } from './config';

// Custom log format
const logFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json(),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    return JSON.stringify({
      timestamp,
      level,
      message,
      service: '{{ service_name }}',
      ...meta,
    });
  })
);

// Create logger instance
export const logger = winston.createLogger({
  level: config.logLevel,
  format: logFormat,
  defaultMeta: { service: '{{ service_name }}' },
  transports: [
    // Console transport
    new winston.transports.Console({
      format: config.nodeEnv === 'development'
        ? winston.format.combine(
            winston.format.colorize(),
            winston.format.simple()
          )
        : logFormat,
    }),

    // File transport for errors
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error',
      format: logFormat,
    }),

    // File transport for all logs
    new winston.transports.File({
      filename: 'logs/combined.log',
      format: logFormat,
    }),
  ],
});

// If not in production, also log to console with simple format
if (config.nodeEnv !== 'production') {
  logger.add(new winston.transports.Console({
    format: winston.format.simple(),
  }));
}
