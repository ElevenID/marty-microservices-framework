package logger

import (
	"os"

	"github.com/sirupsen/logrus"
)

type Logger interface {
	Debug(args ...interface{})
	Debugf(format string, args ...interface{})
	Info(args ...interface{})
	Infof(format string, args ...interface{})
	Warn(args ...interface{})
	Warnf(format string, args ...interface{})
	Error(args ...interface{})
	Errorf(format string, args ...interface{})
	Fatal(args ...interface{})
	Fatalf(format string, args ...interface{})
	WithField(key string, value interface{}) Logger
	WithFields(fields map[string]interface{}) Logger
}

type logrusLogger struct {
	logger *logrus.Logger
	entry  *logrus.Entry
}

func NewLogger(level string) Logger {
	log := logrus.New()

	// Set log level
	logLevel, err := logrus.ParseLevel(level)
	if err != nil {
		logLevel = logrus.InfoLevel
	}
	log.SetLevel(logLevel)

	// Set formatter
	log.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: "2006-01-02T15:04:05.000Z07:00",
	})

	// Set output
	log.SetOutput(os.Stdout)

	return &logrusLogger{
		logger: log,
		entry:  log.WithFields(logrus.Fields{}),
	}
}

func (l *logrusLogger) Debug(args ...interface{}) {
	l.entry.Debug(args...)
}

func (l *logrusLogger) Debugf(format string, args ...interface{}) {
	l.entry.Debugf(format, args...)
}

func (l *logrusLogger) Info(args ...interface{}) {
	l.entry.Info(args...)
}

func (l *logrusLogger) Infof(format string, args ...interface{}) {
	l.entry.Infof(format, args...)
}

func (l *logrusLogger) Warn(args ...interface{}) {
	l.entry.Warn(args...)
}

func (l *logrusLogger) Warnf(format string, args ...interface{}) {
	l.entry.Warnf(format, args...)
}

func (l *logrusLogger) Error(args ...interface{}) {
	l.entry.Error(args...)
}

func (l *logrusLogger) Errorf(format string, args ...interface{}) {
	l.entry.Errorf(format, args...)
}

func (l *logrusLogger) Fatal(args ...interface{}) {
	l.entry.Fatal(args...)
}

func (l *logrusLogger) Fatalf(format string, args ...interface{}) {
	l.entry.Fatalf(format, args...)
}

func (l *logrusLogger) WithField(key string, value interface{}) Logger {
	return &logrusLogger{
		logger: l.logger,
		entry:  l.entry.WithField(key, value),
	}
}

func (l *logrusLogger) WithFields(fields map[string]interface{}) Logger {
	logrusFields := make(logrus.Fields)
	for k, v := range fields {
		logrusFields[k] = v
	}

	return &logrusLogger{
		logger: l.logger,
		entry:  l.entry.WithFields(logrusFields),
	}
}
