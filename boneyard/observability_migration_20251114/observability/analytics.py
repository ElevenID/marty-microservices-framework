"""
Observability Analytics and Insights Engine for Marty Framework

This module provides advanced analytics capabilities for observability data including
performance insights, trend analysis, capacity planning, and intelligent recommendations.
"""

import builtins
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from scipy import stats


class AnalyticsTimeframe(Enum):
    """Analytics timeframe options."""

    REAL_TIME = "real_time"
    LAST_HOUR = "last_hour"
    LAST_DAY = "last_day"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"


class TrendDirection(Enum):
    """Trend direction indicators."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class InsightSeverity(Enum):
    """Insight severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    OPTIMIZATION = "optimization"


@dataclass
class PerformanceInsight:
    """Performance insight with recommendations."""

    id: str
    title: str
    description: str
    severity: InsightSeverity
    metric_name: str
    current_value: float
    expected_value: float | None
    trend: TrendDirection
    confidence: float
    recommendations: builtins.list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class CapacityPrediction:
    """Capacity planning prediction."""

    metric_name: str
    current_usage: float
    predicted_usage: float
    time_to_threshold: timedelta
    confidence_interval: builtins.tuple[float, float]
    recommended_action: str
    prediction_horizon: timedelta
    model_accuracy: float


@dataclass
class AnomalyEvent:
    """Detected anomaly event."""

    id: str
    metric_name: str
    timestamp: datetime
    value: float
    anomaly_score: float
    severity: InsightSeverity
    pattern: str
    context: builtins.dict[str, Any] = field(default_factory=dict)


class PerformanceAnalyzer:
    """Advanced performance analysis and insights."""

    def __init__(self, service_name: str):
        """Initialize performance analyzer."""
        self.service_name = service_name

        # Time series data storage
        self.metric_history: builtins.dict[str, deque] = defaultdict(
            lambda: deque(maxlen=10080)
        )  # 1 week at 1min resolution
        self.performance_baselines: builtins.dict[str, builtins.dict[str, float]] = {}

        # Analysis caches
        self.trend_cache: builtins.dict[str, builtins.tuple[TrendDirection, float]] = {}
        self.seasonal_patterns: builtins.dict[str, builtins.dict[str, float]] = {}
        self.correlation_matrix: builtins.dict[str, builtins.dict[str, float]] = {}

        # Insight generation
        self.insights: deque = deque(maxlen=1000)
        self.insight_templates = self._load_insight_templates()

    def add_metric_data_point(
        self, metric_name: str, value: float, timestamp: datetime | None = None
    ):
        """Add a metric data point for analysis."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        data_point = {"timestamp": timestamp, "value": value}

        self.metric_history[metric_name].append(data_point)

        # Update baselines
        self._update_baselines(metric_name)

        # Invalidate caches
        self._invalidate_caches(metric_name)

    def analyze_performance_trends(
        self, timeframe: AnalyticsTimeframe = AnalyticsTimeframe.LAST_DAY
    ) -> builtins.dict[str, Any]:
        """Analyze performance trends across metrics."""
        results = {}

        for metric_name, history in self.metric_history.items():
            if not history:
                continue

            # Filter data by timeframe
            filtered_data = self._filter_by_timeframe(history, timeframe)

            if len(filtered_data) < 2:
                continue

            # Extract values and timestamps
            values = [dp["value"] for dp in filtered_data]
            timestamps = [dp["timestamp"] for dp in filtered_data]

            # Calculate trend
            trend, confidence = self._calculate_trend(values, timestamps)

            # Calculate statistics
            statistics_data = self._calculate_statistics(values)

            # Detect patterns
            patterns = self._detect_patterns(values, timestamps)

            results[metric_name] = {
                "trend": trend,
                "confidence": confidence,
                "statistics": statistics_data,
                "patterns": patterns,
                "data_points": len(filtered_data),
            }

        return results

    def generate_performance_insights(self) -> builtins.list[PerformanceInsight]:
        """Generate performance insights based on current data."""
        insights = []

        # Analyze each metric
        for metric_name, history in self.metric_history.items():
            if len(history) < 10:  # Need minimum data points
                continue

            # Get recent data
            recent_data = list(history)[-60:]  # Last hour
            values = [dp["value"] for dp in recent_data]

            # Generate various insights
            insights.extend(self._generate_trend_insights(metric_name, values))
            insights.extend(self._generate_threshold_insights(metric_name, values))
            insights.extend(self._generate_efficiency_insights(metric_name, values))
            insights.extend(self._generate_anomaly_insights(metric_name, values))

        # Generate correlation insights
        insights.extend(self._generate_correlation_insights())

        # Store insights
        for insight in insights:
            self.insights.append(insight)

        return insights

    def get_metric_health_score(self, metric_name: str) -> float:
        """Calculate health score for a metric (0-100)."""
        if metric_name not in self.metric_history:
            return 0.0

        history = self.metric_history[metric_name]
        if not history:
            return 0.0

        recent_values = [dp["value"] for dp in list(history)[-60:]]  # Last hour

        # Calculate various health factors
        stability_score = self._calculate_stability_score(recent_values)
        performance_score = self._calculate_performance_score(metric_name, recent_values)
        availability_score = self._calculate_availability_score(recent_values)

        # Weighted combination
        health_score = (
            stability_score * 0.3 + performance_score * 0.5 + availability_score * 0.2
        ) * 100

        return min(100.0, max(0.0, health_score))

    def _filter_by_timeframe(
        self, data: deque, timeframe: AnalyticsTimeframe
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Filter data by timeframe."""
        now = datetime.now(timezone.utc)

        if timeframe == AnalyticsTimeframe.REAL_TIME:
            cutoff = now - timedelta(minutes=5)
        elif timeframe == AnalyticsTimeframe.LAST_HOUR:
            cutoff = now - timedelta(hours=1)
        elif timeframe == AnalyticsTimeframe.LAST_DAY:
            cutoff = now - timedelta(days=1)
        elif timeframe == AnalyticsTimeframe.LAST_WEEK:
            cutoff = now - timedelta(weeks=1)
        elif timeframe == AnalyticsTimeframe.LAST_MONTH:
            cutoff = now - timedelta(days=30)
        else:
            return list(data)

        return [dp for dp in data if dp["timestamp"] >= cutoff]

    def _calculate_trend(
        self, values: builtins.list[float], timestamps: builtins.list[datetime]
    ) -> builtins.tuple[TrendDirection, float]:
        """Calculate trend direction and confidence."""
        if len(values) < 2:
            return TrendDirection.STABLE, 0.0

        # Convert timestamps to numeric for regression
        start_time = timestamps[0]
        x = [(ts - start_time).total_seconds() for ts in timestamps]

        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)

        # Determine trend direction
        if abs(slope) < std_err * 2:  # Not significant
            trend = TrendDirection.STABLE
        elif slope > 0:
            trend = TrendDirection.INCREASING
        else:
            trend = TrendDirection.DECREASING

        # Calculate confidence (based on R-squared and p-value)
        confidence = abs(r_value) * (1 - p_value) if p_value < 0.05 else 0.0

        # Check for volatility
        if len(values) > 5:
            volatility = (
                statistics.stdev(values) / statistics.mean(values)
                if statistics.mean(values) > 0
                else 0
            )
            if volatility > 0.5:  # High volatility threshold
                trend = TrendDirection.VOLATILE
                confidence = min(confidence, 0.5)

        return trend, min(1.0, confidence)

    def _calculate_statistics(self, values: builtins.list[float]) -> builtins.dict[str, float]:
        """Calculate statistical measures."""
        if not values:
            return {}

        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99),
            "coefficient_of_variation": statistics.stdev(values) / statistics.mean(values)
            if statistics.mean(values) > 0 and len(values) > 1
            else 0.0,
        }

    def _detect_patterns(
        self, values: builtins.list[float], timestamps: builtins.list[datetime]
    ) -> builtins.dict[str, Any]:
        """Detect patterns in metric data."""
        if len(values) < 10:
            return {}

        patterns = {}

        # Seasonality detection (simplified)
        if len(values) >= 60:  # Need enough data for hourly patterns
            hourly_means = defaultdict(list)
            for i, timestamp in enumerate(timestamps):
                hour = timestamp.hour
                hourly_means[hour].append(values[i])

            # Calculate variance across hours
            hour_avgs = [statistics.mean(vals) for vals in hourly_means.values() if vals]
            if len(hour_avgs) > 1:
                hourly_variance = statistics.variance(hour_avgs)
                overall_variance = statistics.variance(values)

                if hourly_variance > overall_variance * 0.1:  # Significant hourly pattern
                    patterns["hourly_seasonality"] = True
                    patterns["peak_hours"] = [
                        h
                        for h, vals in hourly_means.items()
                        if vals and statistics.mean(vals) > statistics.mean(values) * 1.2
                    ]

        # Spike detection
        if len(values) > 5:
            mean_val = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0
            threshold = mean_val + 3 * std_dev

            spikes = [i for i, val in enumerate(values) if val > threshold]
            if spikes:
                patterns["spikes_detected"] = len(spikes)
                patterns["spike_severity"] = max(values) / mean_val if mean_val > 0 else 0

        return patterns

    def _generate_trend_insights(
        self, metric_name: str, values: builtins.list[float]
    ) -> builtins.list[PerformanceInsight]:
        """Generate trend-based insights."""
        insights = []

        if len(values) < 5:
            return insights

        # Calculate recent trend
        recent_trend = values[-5:]
        older_values = values[-10:-5] if len(values) >= 10 else values[:-5]

        if not older_values:
            return insights

        recent_avg = statistics.mean(recent_trend)
        older_avg = statistics.mean(older_values)

        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

        if abs(change_percent) > 20:  # Significant change threshold
            severity = InsightSeverity.WARNING if abs(change_percent) > 50 else InsightSeverity.INFO
            direction = "increased" if change_percent > 0 else "decreased"

            insight = PerformanceInsight(
                id=str(uuid4()),
                title=f"{metric_name} trend change detected",
                description=f"{metric_name} has {direction} by {abs(change_percent):.1f}% recently",
                severity=severity,
                metric_name=metric_name,
                current_value=recent_avg,
                expected_value=older_avg,
                trend=TrendDirection.INCREASING
                if change_percent > 0
                else TrendDirection.DECREASING,
                confidence=0.8,
                recommendations=self._get_trend_recommendations(metric_name, change_percent),
                metadata={"change_percent": change_percent},
            )

            insights.append(insight)

        return insights

    def _generate_threshold_insights(
        self, metric_name: str, values: builtins.list[float]
    ) -> builtins.list[PerformanceInsight]:
        """Generate threshold-based insights."""
        insights = []

        if not values:
            return insights

        current_value = values[-1]
        thresholds = self._get_metric_thresholds(metric_name)

        for threshold_name, threshold_value in thresholds.items():
            if current_value > threshold_value:
                severity = self._get_threshold_severity(threshold_name)

                insight = PerformanceInsight(
                    id=str(uuid4()),
                    title=f"{metric_name} exceeds {threshold_name}",
                    description=f"{metric_name} is {current_value:.2f}, which exceeds the {threshold_name} of {threshold_value:.2f}",
                    severity=severity,
                    metric_name=metric_name,
                    current_value=current_value,
                    expected_value=threshold_value,
                    trend=TrendDirection.STABLE,
                    confidence=0.9,
                    recommendations=self._get_threshold_recommendations(
                        metric_name, threshold_name
                    ),
                    metadata={
                        "threshold_type": threshold_name,
                        "threshold_value": threshold_value,
                    },
                )

                insights.append(insight)

        return insights

    def _generate_efficiency_insights(
        self, metric_name: str, values: builtins.list[float]
    ) -> builtins.list[PerformanceInsight]:
        """Generate efficiency-based insights."""
        insights = []

        # Resource efficiency analysis
        if "cpu" in metric_name.lower() or "memory" in metric_name.lower():
            if values and statistics.mean(values) < 0.3:  # Under-utilized
                insight = PerformanceInsight(
                    id=str(uuid4()),
                    title=f"{metric_name} under-utilization detected",
                    description=f"{metric_name} is under-utilized with average usage of {statistics.mean(values):.1%}",
                    severity=InsightSeverity.OPTIMIZATION,
                    metric_name=metric_name,
                    current_value=statistics.mean(values),
                    expected_value=0.7,  # Target utilization
                    trend=TrendDirection.STABLE,
                    confidence=0.7,
                    recommendations=[
                        "Consider reducing allocated resources",
                        "Evaluate if additional workload can be handled",
                        "Review resource allocation strategy",
                    ],
                )
                insights.append(insight)

        return insights

    def _generate_anomaly_insights(
        self, metric_name: str, values: builtins.list[float]
    ) -> builtins.list[PerformanceInsight]:
        """Generate anomaly-based insights."""
        insights = []

        if len(values) < 10:
            return insights

        # Statistical anomaly detection
        mean_val = statistics.mean(values[:-1])  # Exclude current value
        std_dev = statistics.stdev(values[:-1]) if len(values) > 2 else 0
        current_value = values[-1]

        if std_dev > 0:
            z_score = abs(current_value - mean_val) / std_dev

            if z_score > 3:  # Statistical anomaly
                insight = PerformanceInsight(
                    id=str(uuid4()),
                    title=f"Anomaly detected in {metric_name}",
                    description=f"{metric_name} current value {current_value:.2f} is {z_score:.1f} standard deviations from normal",
                    severity=InsightSeverity.WARNING if z_score > 4 else InsightSeverity.INFO,
                    metric_name=metric_name,
                    current_value=current_value,
                    expected_value=mean_val,
                    trend=TrendDirection.VOLATILE,
                    confidence=min(1.0, z_score / 5),
                    recommendations=[
                        "Investigate recent changes",
                        "Check for system events",
                        "Monitor for pattern continuation",
                    ],
                    metadata={"z_score": z_score, "anomaly_type": "statistical"},
                )
                insights.append(insight)

        return insights

    def _generate_correlation_insights(self) -> builtins.list[PerformanceInsight]:
        """Generate correlation-based insights."""
        insights = []

        # Calculate correlations between metrics
        correlations = self._calculate_metric_correlations()

        for (metric1, metric2), correlation in correlations.items():
            if abs(correlation) > 0.8 and metric1 != metric2:  # Strong correlation
                relationship = "positively" if correlation > 0 else "negatively"

                insight = PerformanceInsight(
                    id=str(uuid4()),
                    title=f"Strong correlation between {metric1} and {metric2}",
                    description=f"{metric1} and {metric2} are {relationship} correlated (r={correlation:.2f})",
                    severity=InsightSeverity.INFO,
                    metric_name=metric1,
                    current_value=correlation,
                    expected_value=None,
                    trend=TrendDirection.STABLE,
                    confidence=abs(correlation),
                    recommendations=[
                        "Consider this relationship in capacity planning",
                        "Monitor both metrics together",
                        "Investigate causal relationship",
                    ],
                    metadata={
                        "correlated_metric": metric2,
                        "correlation_coefficient": correlation,
                    },
                )
                insights.append(insight)

        return insights

    def _calculate_metric_correlations(
        self,
    ) -> builtins.dict[builtins.tuple[str, str], float]:
        """Calculate correlations between metrics."""
        correlations = {}
        metric_names = list(self.metric_history.keys())

        for i, metric1 in enumerate(metric_names):
            for metric2 in metric_names[i + 1 :]:
                correlation = self._calculate_correlation(metric1, metric2)
                if correlation is not None:
                    correlations[(metric1, metric2)] = correlation

        return correlations

    def _calculate_correlation(self, metric1: str, metric2: str) -> float | None:
        """Calculate correlation between two metrics."""
        history1 = self.metric_history[metric1]
        history2 = self.metric_history[metric2]

        if len(history1) < 10 or len(history2) < 10:
            return None

        # Align timestamps
        data1 = {dp["timestamp"]: dp["value"] for dp in history1}
        data2 = {dp["timestamp"]: dp["value"] for dp in history2}

        common_timestamps = set(data1.keys()) & set(data2.keys())

        if len(common_timestamps) < 10:
            return None

        values1 = [data1[ts] for ts in common_timestamps]
        values2 = [data2[ts] for ts in common_timestamps]

        try:
            correlation, _ = stats.pearsonr(values1, values2)
            return correlation if not math.isnan(correlation) else None
        except Exception:
            return None

    def _update_baselines(self, metric_name: str):
        """Update performance baselines for a metric."""
        history = self.metric_history[metric_name]

        if len(history) < 60:  # Need minimum data
            return

        values = [dp["value"] for dp in history]

        self.performance_baselines[metric_name] = {
            "mean": statistics.mean(values),
            "p50": self._percentile(values, 0.5),
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    def _invalidate_caches(self, metric_name: str):
        """Invalidate analysis caches for a metric."""
        if metric_name in self.trend_cache:
            del self.trend_cache[metric_name]

    def _calculate_stability_score(self, values: builtins.list[float]) -> float:
        """Calculate stability score (lower variance = higher score)."""
        if len(values) < 2:
            return 1.0

        mean_val = statistics.mean(values)
        if mean_val == 0:
            return 1.0

        cv = statistics.stdev(values) / mean_val
        return max(0.0, 1.0 - cv)

    def _calculate_performance_score(self, metric_name: str, values: builtins.list[float]) -> float:
        """Calculate performance score based on metric type."""
        if not values:
            return 0.0

        current_value = statistics.mean(values)
        baseline = self.performance_baselines.get(metric_name, {})

        if not baseline:
            return 0.5  # Neutral score without baseline

        # For latency metrics (lower is better)
        if "latency" in metric_name.lower() or "response_time" in metric_name.lower():
            baseline_p95 = baseline.get("p95", current_value)
            if baseline_p95 == 0:
                return 1.0
            return max(0.0, 1.0 - (current_value / baseline_p95))

        # For throughput metrics (higher is better)
        if "throughput" in metric_name.lower() or "requests" in metric_name.lower():
            baseline_mean = baseline.get("mean", current_value)
            if baseline_mean == 0:
                return 1.0
            return min(1.0, current_value / baseline_mean)

        # For error metrics (lower is better)
        if "error" in metric_name.lower():
            return max(0.0, 1.0 - current_value)

        # Default: stable around baseline is good
        baseline_mean = baseline.get("mean", current_value)
        baseline_std = baseline.get("std_dev", 1.0)

        if baseline_std == 0:
            return 1.0

        deviation = abs(current_value - baseline_mean) / baseline_std
        return max(0.0, 1.0 - deviation / 3.0)  # 3-sigma rule

    def _calculate_availability_score(self, values: builtins.list[float]) -> float:
        """Calculate availability score (data completeness)."""
        if not values:
            return 0.0

        # Simple availability: percentage of non-zero values
        non_zero_count = sum(1 for v in values if v > 0)
        return non_zero_count / len(values)

    def _get_metric_thresholds(self, metric_name: str) -> builtins.dict[str, float]:
        """Get threshold values for a metric."""
        # Default thresholds - could be configurable
        if "cpu" in metric_name.lower():
            return {"warning": 0.7, "critical": 0.9}
        if "memory" in metric_name.lower():
            return {"warning": 0.8, "critical": 0.95}
        if "error_rate" in metric_name.lower():
            return {"warning": 0.05, "critical": 0.1}
        if "response_time" in metric_name.lower():
            return {"warning": 1000, "critical": 2000}  # milliseconds
        return {}

    def _get_threshold_severity(self, threshold_name: str) -> InsightSeverity:
        """Get severity for threshold type."""
        if threshold_name == "critical":
            return InsightSeverity.CRITICAL
        if threshold_name == "warning":
            return InsightSeverity.WARNING
        return InsightSeverity.INFO

    def _get_trend_recommendations(
        self, metric_name: str, change_percent: float
    ) -> builtins.list[str]:
        """Get recommendations for trend changes."""
        recommendations = []

        if "cpu" in metric_name.lower():
            if change_percent > 0:
                recommendations.extend(
                    [
                        "Monitor for CPU bottlenecks",
                        "Consider horizontal scaling",
                        "Review recent code changes",
                    ]
                )
            else:
                recommendations.extend(
                    [
                        "Good CPU utilization trend",
                        "Consider cost optimization opportunities",
                    ]
                )
        elif "error_rate" in metric_name.lower():
            if change_percent > 0:
                recommendations.extend(
                    [
                        "Investigate error patterns",
                        "Check recent deployments",
                        "Review error logs",
                    ]
                )
        elif "response_time" in metric_name.lower():
            if change_percent > 0:
                recommendations.extend(
                    [
                        "Investigate performance bottlenecks",
                        "Review database query performance",
                        "Check network latency",
                    ]
                )

        return recommendations

    def _get_threshold_recommendations(
        self, metric_name: str, threshold_type: str
    ) -> builtins.list[str]:
        """Get recommendations for threshold violations."""
        recommendations = []

        if "cpu" in metric_name.lower():
            recommendations.extend(
                [
                    "Scale up CPU resources",
                    "Optimize application performance",
                    "Distribute load across instances",
                ]
            )
        elif "memory" in metric_name.lower():
            recommendations.extend(
                [
                    "Increase memory allocation",
                    "Investigate memory leaks",
                    "Optimize memory usage patterns",
                ]
            )
        elif "error_rate" in metric_name.lower():
            recommendations.extend(
                [
                    "Investigate error causes",
                    "Implement circuit breakers",
                    "Review error handling",
                ]
            )

        return recommendations

    def _load_insight_templates(self) -> builtins.dict[str, Any]:
        """Load insight templates for pattern matching."""
        return {
            "performance_degradation": {
                "title_template": "{metric} performance degradation detected",
                "description_template": "{metric} has degraded by {percentage}% in the last {timeframe}",
                "recommendations": [
                    "Investigate recent changes",
                    "Check resource utilization",
                    "Review system logs",
                ],
            },
            "resource_exhaustion": {
                "title_template": "{metric} approaching resource limits",
                "description_template": "{metric} is at {percentage}% of capacity",
                "recommendations": [
                    "Scale resources immediately",
                    "Implement resource monitoring",
                    "Plan capacity expansion",
                ],
            },
        }

    @staticmethod
    def _percentile(data: builtins.list[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]


class CapacityPlanner:
    """Capacity planning and prediction engine."""

    def __init__(self, service_name: str):
        """Initialize capacity planner."""
        self.service_name = service_name
        self.growth_models: builtins.dict[str, Any] = {}
        self.capacity_thresholds: builtins.dict[str, float] = {
            "cpu_usage": 0.8,
            "memory_usage": 0.9,
            "disk_usage": 0.85,
            "network_usage": 0.8,
        }

    def predict_capacity_needs(
        self,
        metric_name: str,
        historical_data: builtins.list[builtins.dict[str, Any]],
        prediction_horizon: timedelta = timedelta(days=30),
    ) -> CapacityPrediction:
        """Predict future capacity needs."""
        if not historical_data or len(historical_data) < 10:
            return self._create_default_prediction(metric_name, prediction_horizon)

        # Extract values and timestamps
        values = [dp["value"] for dp in historical_data]
        timestamps = [dp["timestamp"] for dp in historical_data]

        # Fit growth model
        model_accuracy = self._fit_growth_model(metric_name, values, timestamps)

        # Make prediction
        future_timestamp = timestamps[-1] + prediction_horizon
        predicted_value = self._predict_value(metric_name, future_timestamp, timestamps[0])

        # Calculate confidence interval
        confidence_interval = self._calculate_confidence_interval(metric_name, predicted_value)

        # Determine time to threshold
        threshold = self.capacity_thresholds.get(metric_name, 1.0)
        time_to_threshold = self._calculate_time_to_threshold(
            metric_name, values[-1], threshold, timestamps
        )

        # Generate recommendation
        recommendation = self._generate_capacity_recommendation(
            metric_name, values[-1], predicted_value, threshold
        )

        return CapacityPrediction(
            metric_name=metric_name,
            current_usage=values[-1],
            predicted_usage=predicted_value,
            time_to_threshold=time_to_threshold,
            confidence_interval=confidence_interval,
            recommended_action=recommendation,
            prediction_horizon=prediction_horizon,
            model_accuracy=model_accuracy,
        )

    def _fit_growth_model(
        self,
        metric_name: str,
        values: builtins.list[float],
        timestamps: builtins.list[datetime],
    ) -> float:
        """Fit a growth model to historical data."""
        try:
            # Convert timestamps to numeric (days since start)
            start_time = timestamps[0]
            x = [(ts - start_time).days for ts in timestamps]

            # Try linear regression first
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)

            # Store model
            self.growth_models[metric_name] = {
                "type": "linear",
                "slope": slope,
                "intercept": intercept,
                "r_squared": r_value**2,
                "start_time": start_time,
            }

            return abs(r_value)  # Model accuracy

        except Exception:
            # Fallback to mean model
            self.growth_models[metric_name] = {
                "type": "mean",
                "value": statistics.mean(values),
                "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
            return 0.5  # Moderate accuracy for mean model

    def _predict_value(
        self, metric_name: str, target_timestamp: datetime, start_time: datetime
    ) -> float:
        """Predict value for a future timestamp."""
        model = self.growth_models.get(metric_name)

        if not model:
            return 0.0

        if model["type"] == "linear":
            days_ahead = (target_timestamp - model["start_time"]).days
            return model["slope"] * days_ahead + model["intercept"]
        if model["type"] == "mean":
            return model["value"]

        return 0.0

    def _calculate_confidence_interval(
        self, metric_name: str, predicted_value: float
    ) -> builtins.tuple[float, float]:
        """Calculate confidence interval for prediction."""
        model = self.growth_models.get(metric_name)

        if not model:
            return (predicted_value, predicted_value)

        if model["type"] == "linear":
            # Use R-squared to estimate confidence
            accuracy = model.get("r_squared", 0.5)
            margin = predicted_value * (1 - accuracy) * 0.5  # Simplified margin calculation
            return (max(0, predicted_value - margin), predicted_value + margin)
        if model["type"] == "mean":
            std_dev = model.get("std_dev", 0.0)
            margin = std_dev * 1.96  # 95% confidence interval
            return (max(0, predicted_value - margin), predicted_value + margin)

        return (predicted_value, predicted_value)

    def _calculate_time_to_threshold(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        timestamps: builtins.list[datetime],
    ) -> timedelta:
        """Calculate time until threshold is reached."""
        model = self.growth_models.get(metric_name)

        if not model or current_value >= threshold:
            return timedelta(0)

        if model["type"] == "linear" and model["slope"] > 0:
            # Calculate when linear growth reaches threshold
            days_to_threshold = (threshold - model["intercept"]) / model["slope"]
            current_days = (timestamps[-1] - model["start_time"]).days
            remaining_days = max(0, days_to_threshold - current_days)
            return timedelta(days=remaining_days)

        # Default: assume current growth rate continues
        if len(timestamps) >= 2:
            recent_growth_rate = (
                current_value - 0.8 * current_value
            ) / 7  # Assume some growth over a week
            if recent_growth_rate > 0:
                days_to_threshold = (threshold - current_value) / recent_growth_rate
                return timedelta(days=days_to_threshold)

        return timedelta(days=float("inf"))  # No growth predicted

    def _generate_capacity_recommendation(
        self,
        metric_name: str,
        current_value: float,
        predicted_value: float,
        threshold: float,
    ) -> str:
        """Generate capacity planning recommendation."""
        usage_percentage = (predicted_value / threshold) * 100 if threshold > 0 else 0

        if usage_percentage > 100:
            return f"Immediate action required: {metric_name} will exceed capacity"
        if usage_percentage > 80:
            return f"Plan capacity expansion: {metric_name} approaching limits"
        if usage_percentage > 60:
            return f"Monitor closely: {metric_name} showing growth trend"
        return f"Capacity adequate: {metric_name} within normal ranges"

    def _create_default_prediction(
        self, metric_name: str, prediction_horizon: timedelta
    ) -> CapacityPrediction:
        """Create default prediction when insufficient data."""
        return CapacityPrediction(
            metric_name=metric_name,
            current_usage=0.0,
            predicted_usage=0.0,
            time_to_threshold=timedelta(days=365),  # 1 year default
            confidence_interval=(0.0, 0.0),
            recommended_action="Insufficient data for prediction",
            prediction_horizon=prediction_horizon,
            model_accuracy=0.0,
        )


def create_performance_analyzer(service_name: str) -> PerformanceAnalyzer:
    """Create performance analyzer instance."""
    return PerformanceAnalyzer(service_name)


def create_capacity_planner(service_name: str) -> CapacityPlanner:
    """Create capacity planner instance."""
    return CapacityPlanner(service_name)
