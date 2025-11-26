"""
Comprehensive Performance Report Generator

This module generates visual reports with charts and metrics for:
1. Bottleneck analysis results
2. Timeout detection patterns
3. Audit trail analysis
4. Visual testing results
5. Combined insights and recommendations
"""

import builtins
import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Set style for better looking charts
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


class PerformanceReportGenerator:
    """Generates comprehensive performance reports with visualizations."""

    def __init__(self, report_dir: Path):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(exist_ok=True)
        self.charts_dir = self.report_dir / "charts"
        self.charts_dir.mkdir(exist_ok=True)

        # Configure matplotlib for better output
        plt.rcParams["figure.figsize"] = (12, 8)
        plt.rcParams["font.size"] = 10
        plt.rcParams["axes.titlesize"] = 14
        plt.rcParams["axes.labelsize"] = 12
        plt.rcParams["xtick.labelsize"] = 10
        plt.rcParams["ytick.labelsize"] = 10
        plt.rcParams["legend.fontsize"] = 10

    async def generate_comprehensive_report(
        self,
        bottleneck_report: builtins.dict,
        timeout_report: builtins.dict,
        audit_report: builtins.dict,
        visual_report: builtins.dict,
    ) -> builtins.dict:
        """Generate comprehensive performance report with all test results."""

        print("📊 Generating comprehensive performance report...")

        # Generate individual charts
        chart_files = {}

        # Bottleneck analysis charts
        if bottleneck_report:
            chart_files.update(await self._generate_bottleneck_charts(bottleneck_report))

        # Timeout analysis charts
        if timeout_report:
            chart_files.update(await self._generate_timeout_charts(timeout_report))

        # Audit analysis charts
        if audit_report:
            chart_files.update(await self._generate_audit_charts(audit_report))

        # Visual testing charts
        if visual_report:
            chart_files.update(await self._generate_visual_charts(visual_report))

        # Generate summary dashboard
        summary_chart = await self._generate_summary_dashboard(
            bottleneck_report, timeout_report, audit_report, visual_report
        )
        chart_files["summary_dashboard"] = summary_chart

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            bottleneck_report, timeout_report, audit_report, visual_report
        )

        # Generate recommendations matrix
        recommendations_chart = await self._generate_recommendations_matrix(
            bottleneck_report, timeout_report, audit_report, visual_report
        )
        chart_files["recommendations_matrix"] = recommendations_chart

        # Create comprehensive report
        comprehensive_report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "report_type": "comprehensive_performance_analysis",
                "test_categories": ["bottleneck", "timeout", "audit", "visual"],
                "charts_directory": str(self.charts_dir),
            },
            "executive_summary": executive_summary,
            "test_results_summary": {
                "bottleneck_analysis": self._summarize_bottleneck_results(bottleneck_report),
                "timeout_detection": self._summarize_timeout_results(timeout_report),
                "audit_analysis": self._summarize_audit_results(audit_report),
                "visual_testing": self._summarize_visual_results(visual_report),
            },
            "performance_insights": self._generate_cross_cutting_insights(
                bottleneck_report, timeout_report, audit_report, visual_report
            ),
            "charts_generated": chart_files,
            "actionable_recommendations": self._consolidate_recommendations(
                bottleneck_report, timeout_report, audit_report, visual_report
            ),
        }

        # Save comprehensive report
        report_file = self.report_dir / "comprehensive_performance_report.json"
        with open(report_file, "w") as f:
            json.dump(comprehensive_report, f, indent=2)

        # Generate HTML report
        html_report = await self._generate_html_report(comprehensive_report)
        html_file = self.report_dir / "performance_report.html"
        with open(html_file, "w") as f:
            f.write(html_report)

        print("✅ Comprehensive report generated:")
        print(f"   📄 JSON: {report_file}")
        print(f"   🌐 HTML: {html_file}")
        print(f"   📊 Charts: {len(chart_files)} charts in {self.charts_dir}")

        return comprehensive_report

    async def _generate_bottleneck_charts(
        self, bottleneck_report: builtins.dict
    ) -> builtins.dict[str, str]:
        """Generate charts for bottleneck analysis."""
        charts = {}

        if not bottleneck_report or "performance_trends" not in bottleneck_report:
            return charts

        trends = bottleneck_report["performance_trends"]

        # CPU and Memory Usage Trends
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # CPU Usage Chart
        if "cpu_usage_by_load" in trends:
            load_levels = list(trends["cpu_usage_by_load"].keys())
            cpu_values = list(trends["cpu_usage_by_load"].values())

            ax1.plot(
                load_levels,
                cpu_values,
                marker="o",
                linewidth=2,
                markersize=8,
                color="#e74c3c",
            )
            ax1.axhline(
                y=80,
                color="red",
                linestyle="--",
                alpha=0.7,
                label="Critical Threshold (80%)",
            )
            ax1.set_title("CPU Usage Under Different Load Levels", fontweight="bold")
            ax1.set_xlabel("Load Level")
            ax1.set_ylabel("CPU Usage (%)")
            ax1.grid(True, alpha=0.3)
            ax1.legend()

        # Memory Usage Chart
        if "memory_usage_by_load" in trends:
            load_levels = list(trends["memory_usage_by_load"].keys())
            memory_values = list(trends["memory_usage_by_load"].values())

            ax2.plot(
                load_levels,
                memory_values,
                marker="s",
                linewidth=2,
                markersize=8,
                color="#3498db",
            )
            ax2.axhline(
                y=85,
                color="orange",
                linestyle="--",
                alpha=0.7,
                label="Warning Threshold (85%)",
            )
            ax2.set_title("Memory Usage Under Different Load Levels", fontweight="bold")
            ax2.set_xlabel("Load Level")
            ax2.set_ylabel("Memory Usage (%)")
            ax2.grid(True, alpha=0.3)
            ax2.legend()

        plt.tight_layout()
        cpu_memory_chart = self.charts_dir / "bottleneck_cpu_memory_trends.png"
        plt.savefig(cpu_memory_chart, dpi=300, bbox_inches="tight")
        plt.close()
        charts["cpu_memory_trends"] = str(cpu_memory_chart)

        # Bottleneck Types Distribution
        if "bottleneck_analysis" in bottleneck_report:
            bottleneck_types = bottleneck_report["bottleneck_analysis"].get("bottleneck_types", {})

            if bottleneck_types:
                fig, ax = plt.subplots(figsize=(10, 6))

                types = list(bottleneck_types.keys())
                counts = list(bottleneck_types.values())
                colors = ["#e74c3c", "#3498db", "#f39c12", "#27ae60"]

                bars = ax.bar(types, counts, color=colors[: len(types)])
                ax.set_title("Bottleneck Types Distribution", fontweight="bold")
                ax.set_xlabel("Bottleneck Type")
                ax.set_ylabel("Number of Occurrences")
                ax.grid(True, alpha=0.3, axis="y")

                # Add value labels on bars
                for bar, count in zip(bars, counts, strict=False):
                    if count > 0:
                        ax.text(
                            bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.1,
                            str(count),
                            ha="center",
                            va="bottom",
                            fontweight="bold",
                        )

                plt.tight_layout()
                bottleneck_dist_chart = self.charts_dir / "bottleneck_types_distribution.png"
                plt.savefig(bottleneck_dist_chart, dpi=300, bbox_inches="tight")
                plt.close()
                charts["bottleneck_distribution"] = str(bottleneck_dist_chart)

        return charts

    async def _generate_timeout_charts(
        self, timeout_report: builtins.dict
    ) -> builtins.dict[str, str]:
        """Generate charts for timeout analysis."""
        charts = {}

        if not timeout_report or "timeout_patterns" not in timeout_report:
            return charts

        patterns = timeout_report["timeout_patterns"]

        # Timeout Progression Chart
        if "timeout_progression" in patterns:
            progression = patterns["timeout_progression"]

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

            phases = [p["phase"] for p in progression]
            timeout_rates = [p["timeout_rate"] for p in progression]
            absolute_timeouts = [p["absolute_timeouts"] for p in progression]

            # Timeout Rate Chart
            ax1.plot(
                phases,
                timeout_rates,
                marker="o",
                linewidth=3,
                markersize=10,
                color="#e74c3c",
            )
            ax1.fill_between(phases, timeout_rates, alpha=0.3, color="#e74c3c")
            ax1.set_title("Timeout Rate Progression Across Test Phases", fontweight="bold")
            ax1.set_xlabel("Test Phase")
            ax1.set_ylabel("Timeout Rate (%)")
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis="x", rotation=45)

            # Absolute Timeouts Chart
            bars = ax2.bar(phases, absolute_timeouts, color="#f39c12", alpha=0.7)
            ax2.set_title("Absolute Timeout Counts by Phase", fontweight="bold")
            ax2.set_xlabel("Test Phase")
            ax2.set_ylabel("Number of Timeouts")
            ax2.grid(True, alpha=0.3, axis="y")
            ax2.tick_params(axis="x", rotation=45)

            # Add value labels on bars
            for bar, count in zip(bars, absolute_timeouts, strict=False):
                if count > 0:
                    ax2.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.1,
                        str(count),
                        ha="center",
                        va="bottom",
                        fontweight="bold",
                    )

            plt.tight_layout()
            timeout_progression_chart = self.charts_dir / "timeout_progression.png"
            plt.savefig(timeout_progression_chart, dpi=300, bbox_inches="tight")
            plt.close()
            charts["timeout_progression"] = str(timeout_progression_chart)

        # Circuit Breaker Effectiveness Chart
        if "circuit_breaker_effectiveness" in patterns:
            cb_data = patterns["circuit_breaker_effectiveness"]

            fig, ax = plt.subplots(figsize=(10, 6))

            phases = [cb["phase"] for cb in cb_data]
            trip_rates = [cb["trip_rate"] for cb in cb_data]

            bars = ax.bar(phases, trip_rates, color="#27ae60", alpha=0.7)
            ax.axhline(
                y=0.8,
                color="green",
                linestyle="--",
                alpha=0.7,
                label="Effective Threshold (80%)",
            )
            ax.set_title("Circuit Breaker Effectiveness by Phase", fontweight="bold")
            ax.set_xlabel("Test Phase")
            ax.set_ylabel("Trip Rate (effectiveness)")
            ax.set_ylim(0, 1.1)
            ax.grid(True, alpha=0.3, axis="y")
            ax.legend()
            ax.tick_params(axis="x", rotation=45)

            # Add percentage labels
            for bar, rate in zip(bars, trip_rates, strict=False):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.02,
                    f"{rate:.1%}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                )

            plt.tight_layout()
            cb_effectiveness_chart = self.charts_dir / "circuit_breaker_effectiveness.png"
            plt.savefig(cb_effectiveness_chart, dpi=300, bbox_inches="tight")
            plt.close()
            charts["circuit_breaker_effectiveness"] = str(cb_effectiveness_chart)

        return charts

    async def _generate_audit_charts(self, audit_report: builtins.dict) -> builtins.dict[str, str]:
        """Generate charts for audit analysis."""
        charts = {}

        if not audit_report or "audit_quality_metrics" not in audit_report:
            return charts

        # Event Types Distribution
        if "compliance_report" in audit_report:
            event_summary = audit_report["compliance_report"].get("event_summary", {})

            if event_summary:
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

                # Event Types Pie Chart
                event_types = [
                    "Error Events",
                    "Business Events",
                    "Security Events",
                    "Performance Events",
                ]
                event_counts = [
                    event_summary.get("error_events", 0),
                    event_summary.get("business_events", 0),
                    event_summary.get("security_events", 0),
                    event_summary.get("performance_events", 0),
                ]

                colors = ["#e74c3c", "#3498db", "#f39c12", "#27ae60"]
                wedges, texts, autotexts = ax1.pie(
                    event_counts,
                    labels=event_types,
                    colors=colors,
                    autopct="%1.1f%%",
                    startangle=90,
                    textprops={"fontsize": 10},
                )
                ax1.set_title("Audit Events Distribution by Type", fontweight="bold")

                # Quality Metrics Bar Chart
                quality = audit_report["audit_quality_metrics"]
                metrics = ["Completeness", "Traceability"]
                scores = [
                    quality.get("completeness_score", 0) * 100,
                    quality.get("traceability_score", 0) * 100,
                ]

                bars = ax2.bar(metrics, scores, color=["#9b59b6", "#1abc9c"], alpha=0.7)
                ax2.axhline(
                    y=80,
                    color="green",
                    linestyle="--",
                    alpha=0.7,
                    label="Good Threshold (80%)",
                )
                ax2.set_title("Audit Quality Metrics", fontweight="bold")
                ax2.set_ylabel("Score (%)")
                ax2.set_ylim(0, 100)
                ax2.grid(True, alpha=0.3, axis="y")
                ax2.legend()

                # Add percentage labels
                for bar, score in zip(bars, scores, strict=False):
                    ax2.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 1,
                        f"{score:.1f}%",
                        ha="center",
                        va="bottom",
                        fontweight="bold",
                    )

                plt.tight_layout()
                audit_overview_chart = self.charts_dir / "audit_overview.png"
                plt.savefig(audit_overview_chart, dpi=300, bbox_inches="tight")
                plt.close()
                charts["audit_overview"] = str(audit_overview_chart)

        # Compliance Checks Chart
        if (
            "compliance_report" in audit_report
            and "compliance_checks" in audit_report["compliance_report"]
        ):
            compliance_checks = audit_report["compliance_report"]["compliance_checks"]

            fig, ax = plt.subplots(figsize=(12, 6))

            check_names = [check["check"].replace("_", " ").title() for check in compliance_checks]
            check_status = [
                "Passed" if check["passed"] else "Failed" for check in compliance_checks
            ]

            # Create color map
            colors = ["#27ae60" if status == "Passed" else "#e74c3c" for status in check_status]

            bars = ax.barh(check_names, [1] * len(check_names), color=colors, alpha=0.7)
            ax.set_title("Compliance Checks Status", fontweight="bold")
            ax.set_xlabel("Status")
            ax.set_xlim(0, 1.2)

            # Add status labels
            for i, (_bar, status) in enumerate(zip(bars, check_status, strict=False)):
                ax.text(
                    0.5,
                    i,
                    status,
                    ha="center",
                    va="center",
                    fontweight="bold",
                    color="white",
                )

            plt.tight_layout()
            compliance_chart = self.charts_dir / "compliance_status.png"
            plt.savefig(compliance_chart, dpi=300, bbox_inches="tight")
            plt.close()
            charts["compliance_status"] = str(compliance_chart)

        return charts

    async def _generate_visual_charts(
        self, visual_report: builtins.dict
    ) -> builtins.dict[str, str]:
        """Generate charts for visual testing results."""
        charts = {}

        if not visual_report or "visual_quality_metrics" not in visual_report:
            return charts

        quality_metrics = visual_report["visual_quality_metrics"]

        # Visual Quality Scorecard
        fig, ax = plt.subplots(figsize=(10, 8))

        metrics = [
            "Dashboard Loads",
            "Responsive Design",
            "Interactive Elements",
            "Metrics Display",
            "Accessibility",
        ]

        values = [
            1 if quality_metrics.get("dashboard_loads_successfully", False) else 0,
            1 if quality_metrics.get("responsive_across_devices", False) else 0,
            1 if quality_metrics.get("interactive_elements_functional", False) else 0,
            1 if quality_metrics.get("metrics_display_accurate", False) else 0,
            1 if quality_metrics.get("accessibility_compliant", False) else 0,
        ]

        colors = ["#27ae60" if v == 1 else "#e74c3c" for v in values]

        bars = ax.barh(metrics, values, color=colors, alpha=0.7)
        ax.set_title("Visual Testing Quality Scorecard", fontweight="bold")
        ax.set_xlabel("Pass/Fail Status")
        ax.set_xlim(0, 1.2)

        # Add status labels
        for i, (_bar, value) in enumerate(zip(bars, values, strict=False)):
            status = "PASS" if value == 1 else "FAIL"
            ax.text(
                0.5,
                i,
                status,
                ha="center",
                va="center",
                fontweight="bold",
                color="white",
            )

        plt.tight_layout()
        visual_scorecard_chart = self.charts_dir / "visual_testing_scorecard.png"
        plt.savefig(visual_scorecard_chart, dpi=300, bbox_inches="tight")
        plt.close()
        charts["visual_scorecard"] = str(visual_scorecard_chart)

        return charts

    async def _generate_summary_dashboard(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ) -> str:
        """Generate a comprehensive summary dashboard."""

        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # Overall Health Score (Top Center)
        ax_health = fig.add_subplot(gs[0, 1])
        overall_score = self._calculate_overall_health_score(
            bottleneck_report, timeout_report, audit_report, visual_report
        )

        # Create a gauge-like visualization
        colors = ["#e74c3c", "#f39c12", "#27ae60"]
        color_idx = 0 if overall_score < 60 else 1 if overall_score < 80 else 2

        wedges, texts = ax_health.pie(
            [overall_score, 100 - overall_score],
            colors=[colors[color_idx], "#ecf0f1"],
            startangle=90,
            counterclock=False,
        )
        ax_health.text(
            0,
            0,
            f"{overall_score:.0f}%",
            ha="center",
            va="center",
            fontsize=20,
            fontweight="bold",
        )
        ax_health.set_title("Overall Health Score", fontweight="bold", fontsize=14)

        # Test Categories Summary (Top Row)
        test_scores = {
            "Bottleneck": self._get_test_score(bottleneck_report),
            "Timeout": self._get_test_score(timeout_report),
            "Audit": self._get_test_score(audit_report),
            "Visual": self._get_test_score(visual_report),
        }

        # Bottleneck Summary (Top Left)
        ax_bottleneck = fig.add_subplot(gs[0, 0])
        self._create_mini_chart(ax_bottleneck, "Bottleneck Analysis", test_scores["Bottleneck"])

        # Visual Testing Summary (Top Right)
        ax_visual = fig.add_subplot(gs[0, 2])
        self._create_mini_chart(ax_visual, "Visual Testing", test_scores["Visual"])

        # Performance Trends (Middle Left)
        ax_trends = fig.add_subplot(gs[1, 0])
        if bottleneck_report and "performance_trends" in bottleneck_report:
            trends = bottleneck_report["performance_trends"]
            if "cpu_usage_by_load" in trends:
                loads = list(trends["cpu_usage_by_load"].keys())
                cpu_vals = list(trends["cpu_usage_by_load"].values())
                ax_trends.plot(loads, cpu_vals, "o-", color="#e74c3c", linewidth=2)
                ax_trends.set_title("CPU Usage Trend", fontweight="bold")
                ax_trends.set_ylabel("CPU %")
                ax_trends.grid(True, alpha=0.3)

        # Timeout Analysis (Middle Center)
        ax_timeout = fig.add_subplot(gs[1, 1])
        if timeout_report and "timeout_patterns" in timeout_report:
            patterns = timeout_report["timeout_patterns"]
            if "timeout_progression" in patterns:
                progression = patterns["timeout_progression"]
                phases = [p["phase"] for p in progression]
                rates = [p["timeout_rate"] for p in progression]
                ax_timeout.bar(phases, rates, color="#f39c12", alpha=0.7)
                ax_timeout.set_title("Timeout Rates", fontweight="bold")
                ax_timeout.set_ylabel("Rate %")
                ax_timeout.tick_params(axis="x", rotation=45)

        # Audit Quality (Middle Right)
        ax_audit = fig.add_subplot(gs[1, 2])
        if audit_report and "audit_quality_metrics" in audit_report:
            quality = audit_report["audit_quality_metrics"]
            completeness = quality.get("completeness_score", 0) * 100
            traceability = quality.get("traceability_score", 0) * 100

            metrics = ["Completeness", "Traceability"]
            scores = [completeness, traceability]
            ax_audit.bar(metrics, scores, color=["#9b59b6", "#1abc9c"], alpha=0.7)
            ax_audit.set_title("Audit Quality", fontweight="bold")
            ax_audit.set_ylabel("Score %")
            ax_audit.set_ylim(0, 100)

        # Critical Issues Summary (Bottom Row)
        ax_issues = fig.add_subplot(gs[2, :])
        critical_issues = self._collect_critical_issues(
            bottleneck_report, timeout_report, audit_report, visual_report
        )

        if critical_issues:
            issue_text = "\\n".join([f"• {issue}" for issue in critical_issues[:5]])
            ax_issues.text(
                0.05,
                0.95,
                "Critical Issues Identified:",
                transform=ax_issues.transAxes,
                fontweight="bold",
                fontsize=12,
                va="top",
            )
            ax_issues.text(
                0.05,
                0.85,
                issue_text,
                transform=ax_issues.transAxes,
                fontsize=10,
                va="top",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "#f8d7da", "alpha": 0.7},
            )
        else:
            ax_issues.text(
                0.5,
                0.5,
                "✅ No Critical Issues Detected",
                transform=ax_issues.transAxes,
                fontsize=14,
                ha="center",
                va="center",
                fontweight="bold",
                color="#27ae60",
            )

        ax_issues.set_xlim(0, 1)
        ax_issues.set_ylim(0, 1)
        ax_issues.axis("off")

        plt.suptitle(
            "🚀 Marty Framework - Performance Analysis Dashboard",
            fontsize=16,
            fontweight="bold",
            y=0.98,
        )

        summary_dashboard_chart = self.charts_dir / "summary_dashboard.png"
        plt.savefig(summary_dashboard_chart, dpi=300, bbox_inches="tight")
        plt.close()

        return str(summary_dashboard_chart)

    def _create_mini_chart(self, ax, title, score):
        """Create a mini chart for the summary dashboard."""
        color = "#e74c3c" if score < 60 else "#f39c12" if score < 80 else "#27ae60"
        ax.bar(["Score"], [score], color=color, alpha=0.7)
        ax.set_title(title, fontweight="bold")
        ax.set_ylim(0, 100)
        ax.set_ylabel("%")
        ax.text(0, score + 2, f"{score:.0f}%", ha="center", va="bottom", fontweight="bold")

    async def _generate_recommendations_matrix(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ) -> str:
        """Generate a recommendations priority matrix."""

        # Collect all recommendations
        all_recommendations = []

        for report_type, report in [
            ("Bottleneck", bottleneck_report),
            ("Timeout", timeout_report),
            ("Audit", audit_report),
            ("Visual", visual_report),
        ]:
            if report and "recommendations" in report:
                for rec in report["recommendations"]:
                    all_recommendations.append(
                        {
                            "source": report_type,
                            "category": rec["category"],
                            "priority": rec["priority"],
                            "action_count": len(rec.get("actions", [])),
                        }
                    )

        if not all_recommendations:
            # Create empty chart
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                "No recommendations generated",
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.axis("off")
            recommendations_chart = self.charts_dir / "recommendations_matrix.png"
            plt.savefig(recommendations_chart, dpi=300, bbox_inches="tight")
            plt.close()
            return str(recommendations_chart)

        # Create recommendations matrix
        fig, ax = plt.subplots(figsize=(12, 8))

        # Group by priority and category
        priority_order = ["critical", "high", "medium", "low"]
        list({rec["category"] for rec in all_recommendations})

        # Create matrix data
        matrix_data = []
        y_labels = []

        for priority in priority_order:
            priority_recs = [r for r in all_recommendations if r["priority"] == priority]
            if priority_recs:
                for rec in priority_recs:
                    matrix_data.append(rec["action_count"])
                    y_labels.append(f"{rec['category']}\\n({priority})")

        if matrix_data:
            # Create horizontal bar chart
            colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(matrix_data)))
            bars = ax.barh(range(len(matrix_data)), matrix_data, color=colors)

            ax.set_yticks(range(len(matrix_data)))
            ax.set_yticklabels(y_labels, fontsize=10)
            ax.set_xlabel("Number of Actions Required")
            ax.set_title("Recommendations Priority Matrix", fontweight="bold", fontsize=14)
            ax.grid(True, alpha=0.3, axis="x")

            # Add value labels
            for _i, (bar, count) in enumerate(zip(bars, matrix_data, strict=False)):
                ax.text(
                    bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    str(count),
                    va="center",
                    fontweight="bold",
                )

        plt.tight_layout()
        recommendations_chart = self.charts_dir / "recommendations_matrix.png"
        plt.savefig(recommendations_chart, dpi=300, bbox_inches="tight")
        plt.close()

        return str(recommendations_chart)

    def _calculate_overall_health_score(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ):
        """Calculate overall health score from all test results."""
        scores = []

        # Bottleneck score (inverse of issues)
        if bottleneck_report and "summary" in bottleneck_report:
            critical_bottlenecks = bottleneck_report["summary"].get("critical_bottlenecks", 0)
            bottleneck_score = max(0, 100 - (critical_bottlenecks * 20))
            scores.append(bottleneck_score)

        # Timeout score
        if timeout_report and "test_summary" in timeout_report:
            timeout_rate = timeout_report["test_summary"].get("overall_timeout_rate", 0)
            timeout_score = max(0, 100 - (timeout_rate * 5))
            scores.append(timeout_score)

        # Audit score
        if audit_report and "audit_quality_metrics" in audit_report:
            quality = audit_report["audit_quality_metrics"]
            completeness = quality.get("completeness_score", 0) * 100
            traceability = quality.get("traceability_score", 0) * 100
            audit_score = (completeness + traceability) / 2
            scores.append(audit_score)

        # Visual score
        if visual_report and "test_summary" in visual_report:
            success_rate = visual_report["test_summary"].get("success_rate", 0)
            scores.append(success_rate)

        return sum(scores) / len(scores) if scores else 50

    def _get_test_score(self, report):
        """Get a simple score for a test category."""
        if not report:
            return 0

        # Simple scoring based on presence of critical issues
        if "summary" in report:
            if "critical_bottlenecks" in report["summary"]:
                return max(0, 100 - (report["summary"]["critical_bottlenecks"] * 25))

        if "test_summary" in report:
            if "success_rate" in report["test_summary"]:
                return report["test_summary"]["success_rate"]
            if "overall_timeout_rate" in report["test_summary"]:
                return max(0, 100 - (report["test_summary"]["overall_timeout_rate"] * 5))

        if "audit_quality_metrics" in report:
            quality = report["audit_quality_metrics"]
            return (
                quality.get("completeness_score", 0) + quality.get("traceability_score", 0)
            ) * 50

        return 75  # Default decent score

    def _collect_critical_issues(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ):
        """Collect critical issues from all reports."""
        issues = []

        # Bottleneck critical issues
        if bottleneck_report and "bottleneck_analysis" in bottleneck_report:
            critical_bottlenecks = bottleneck_report["bottleneck_analysis"].get(
                "critical_bottlenecks", []
            )
            for bottleneck in critical_bottlenecks[:2]:  # Top 2
                if bottleneck.get("severity") == "critical":
                    issues.append(
                        f"Critical {bottleneck['type']} bottleneck in {bottleneck['service']}"
                    )

        # Timeout critical issues
        if timeout_report and "insights" in timeout_report:
            for insight in timeout_report["insights"]:
                if insight.get("severity") == "critical":
                    issues.append(f"Timeout issue: {insight['message']}")

        # Audit critical issues
        if audit_report and "compliance_report" in audit_report:
            compliance_checks = audit_report["compliance_report"].get("compliance_checks", [])
            failed_checks = [c for c in compliance_checks if not c["passed"]]
            if failed_checks:
                issues.append(f"{len(failed_checks)} compliance checks failed")

        # Visual critical issues
        if visual_report and "visual_quality_metrics" in visual_report:
            quality = visual_report["visual_quality_metrics"]
            if not quality.get("dashboard_loads_successfully", True):
                issues.append("Dashboard fails to load properly")

        return issues

    def _summarize_bottleneck_results(self, report):
        """Summarize bottleneck analysis results."""
        if not report:
            return {
                "status": "not_run",
                "summary": "Bottleneck analysis was not executed",
            }

        summary = report.get("test_summary", {})
        return {
            "status": "completed",
            "load_levels_tested": summary.get("load_levels_tested", []),
            "total_bottlenecks": summary.get("total_bottlenecks", 0),
            "critical_bottlenecks": summary.get("critical_bottlenecks", 0),
        }

    def _summarize_timeout_results(self, report):
        """Summarize timeout detection results."""
        if not report:
            return {
                "status": "not_run",
                "summary": "Timeout detection was not executed",
            }

        summary = report.get("test_summary", {})
        return {
            "status": "completed",
            "phases_tested": summary.get("phases_tested", []),
            "total_timeouts": summary.get("total_timeouts", 0),
            "timeout_rate": summary.get("overall_timeout_rate", 0),
        }

    def _summarize_audit_results(self, report):
        """Summarize audit analysis results."""
        if not report:
            return {"status": "not_run", "summary": "Audit analysis was not executed"}

        summary = report.get("test_summary", {})
        quality = report.get("audit_quality_metrics", {})
        return {
            "status": "completed",
            "total_events": summary.get("total_events_generated", 0),
            "completeness_score": quality.get("completeness_score", 0),
            "traceability_score": quality.get("traceability_score", 0),
        }

    def _summarize_visual_results(self, report):
        """Summarize visual testing results."""
        if not report:
            return {"status": "not_run", "summary": "Visual testing was not executed"}

        summary = report.get("test_summary", {})
        return {
            "status": "completed",
            "success_rate": summary.get("success_rate", 0),
            "categories_tested": summary.get("total_test_categories", 0),
            "screenshots_generated": len(report.get("screenshots_generated", [])),
        }

    def _generate_cross_cutting_insights(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ):
        """Generate insights that span across multiple test categories."""
        insights = []

        # Performance correlation insights
        has_cpu_bottleneck = False
        has_high_timeouts = False

        if bottleneck_report and "bottleneck_analysis" in bottleneck_report:
            cpu_bottlenecks = [
                b
                for b in bottleneck_report["bottleneck_analysis"].get("critical_bottlenecks", [])
                if b.get("type") == "cpu"
            ]
            has_cpu_bottleneck = len(cpu_bottlenecks) > 0

        if timeout_report and "test_summary" in timeout_report:
            timeout_rate = timeout_report["test_summary"].get("overall_timeout_rate", 0)
            has_high_timeouts = timeout_rate > 10

        if has_cpu_bottleneck and has_high_timeouts:
            insights.append(
                {
                    "type": "performance_correlation",
                    "message": "CPU bottlenecks are strongly correlated with timeout issues",
                    "severity": "high",
                    "recommendation": "Focus on CPU optimization to reduce both bottlenecks and timeouts",
                }
            )

        # Audit and error correlation
        if audit_report and "error_analysis" in audit_report:
            error_patterns = audit_report["error_analysis"].get("patterns", [])
            if error_patterns:
                services_with_errors = [p["service"] for p in error_patterns]

                if bottleneck_report and "bottleneck_analysis" in bottleneck_report:
                    bottlenecked_services = [
                        b["service"]
                        for b in bottleneck_report["bottleneck_analysis"].get(
                            "critical_bottlenecks", []
                        )
                    ]

                    common_services = set(services_with_errors) & set(bottlenecked_services)
                    if common_services:
                        insights.append(
                            {
                                "type": "error_performance_correlation",
                                "message": f"Services {list(common_services)} show both performance and error issues",
                                "severity": "critical",
                                "recommendation": "Prioritize these services for immediate optimization",
                            }
                        )

        return insights

    def _consolidate_recommendations(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ):
        """Consolidate recommendations from all test categories."""
        all_recommendations = []

        # Collect recommendations from each report
        for report_name, report in [
            ("bottleneck", bottleneck_report),
            ("timeout", timeout_report),
            ("audit", audit_report),
            ("visual", visual_report),
        ]:
            if report and "recommendations" in report:
                for rec in report["recommendations"]:
                    rec["source"] = report_name
                    all_recommendations.append(rec)

        # Prioritize and deduplicate
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))

        # Group similar recommendations
        consolidated = {}
        for rec in all_recommendations:
            category = rec.get("category", "General")
            if category not in consolidated:
                consolidated[category] = {
                    "category": category,
                    "priority": rec.get("priority", "medium"),
                    "sources": [],
                    "actions": [],
                }

            consolidated[category]["sources"].append(rec["source"])
            consolidated[category]["actions"].extend(rec.get("actions", []))

            # Use highest priority
            current_priority = priority_order.get(consolidated[category]["priority"], 3)
            new_priority = priority_order.get(rec.get("priority", "medium"), 3)
            if new_priority < current_priority:
                consolidated[category]["priority"] = rec.get("priority", "medium")

        # Remove duplicates and limit actions
        for category in consolidated:
            consolidated[category]["actions"] = list(set(consolidated[category]["actions"]))[:5]
            consolidated[category]["sources"] = list(set(consolidated[category]["sources"]))

        return list(consolidated.values())

    def _generate_executive_summary(
        self, bottleneck_report, timeout_report, audit_report, visual_report
    ):
        """Generate executive summary of all test results."""

        overall_score = self._calculate_overall_health_score(
            bottleneck_report, timeout_report, audit_report, visual_report
        )

        # Determine overall status
        if overall_score >= 80:
            status = "excellent"
            status_message = "System demonstrates excellent performance and reliability"
        elif overall_score >= 60:
            status = "good"
            status_message = "System shows good performance with some areas for improvement"
        else:
            status = "needs_attention"
            status_message = "System requires immediate attention to address performance issues"

        # Count critical issues
        critical_issues = self._collect_critical_issues(
            bottleneck_report, timeout_report, audit_report, visual_report
        )

        return {
            "overall_health_score": overall_score,
            "status": status,
            "status_message": status_message,
            "critical_issues_count": len(critical_issues),
            "tests_executed": {
                "bottleneck_analysis": bottleneck_report is not None,
                "timeout_detection": timeout_report is not None,
                "audit_analysis": audit_report is not None,
                "visual_testing": visual_report is not None,
            },
            "key_findings": critical_issues[:3],  # Top 3 critical issues
            "recommended_next_steps": self._get_next_steps(overall_score, critical_issues),
        }

    def _get_next_steps(self, overall_score, critical_issues):
        """Get recommended next steps based on analysis."""
        if overall_score >= 80 and len(critical_issues) == 0:
            return [
                "Continue monitoring with current test suite",
                "Consider expanding test coverage to edge cases",
                "Document current best practices for team reference",
            ]
        if overall_score >= 60:
            return [
                "Address identified performance bottlenecks",
                "Implement recommended optimizations",
                "Increase monitoring frequency for at-risk services",
            ]
        return [
            "Immediately address all critical issues",
            "Implement emergency performance optimizations",
            "Establish daily monitoring and review cycles",
            "Consider scaling resources for high-load services",
        ]

    async def _generate_html_report(self, comprehensive_report: builtins.dict) -> str:
        """Generate HTML version of the comprehensive report."""

        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Marty Framework - Performance Analysis Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .content {
            padding: 30px;
        }
        .executive-summary {
            background: #f8f9fa;
            border-left: 5px solid #28a745;
            padding: 20px;
            margin-bottom: 30px;
            border-radius: 0 5px 5px 0;
        }
        .health-score {
            text-align: center;
            margin: 20px 0;
        }
        .score-circle {
            display: inline-block;
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: conic-gradient(#28a745 {score_percentage}%, #e9ecef {score_percentage}%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            color: #2d3436;
            margin: 0 auto;
        }
        .test-results {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .test-card {
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .test-card h3 {
            color: #495057;
            margin-top: 0;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-excellent { background: #d4edda; color: #155724; }
        .status-good { background: #fff3cd; color: #856404; }
        .status-needs_attention { background: #f8d7da; color: #721c24; }
        .charts-section {
            margin: 30px 0;
        }
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .chart-item img {
            width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .recommendations {
            background: #e3f2fd;
            border-radius: 8px;
            padding: 20px;
            margin: 30px 0;
        }
        .recommendation-item {
            background: white;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #2196f3;
        }
        .priority-critical { border-left-color: #f44336; }
        .priority-high { border-left-color: #ff9800; }
        .priority-medium { border-left-color: #2196f3; }
        .priority-low { border-left-color: #4caf50; }
        .footer {
            background: #343a40;
            color: white;
            text-align: center;
            padding: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #dee2e6;
            padding: 12px;
            text-align: left;
        }
        th {
            background: #f8f9fa;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Marty Framework</h1>
            <p>Comprehensive Performance Analysis Report</p>
            <p>Generated on {generation_time}</p>
        </div>

        <div class="content">
            <div class="executive-summary">
                <h2>Executive Summary</h2>
                <div class="health-score">
                    <div class="score-circle">
                        {overall_score}%
                    </div>
                    <p><strong>Overall Health Score</strong></p>
                    <span class="status-badge status-{status}">{status_message}</span>
                </div>

                {critical_issues_section}

                <h3>Key Findings</h3>
                <ul>
                    {key_findings_list}
                </ul>

                <h3>Recommended Next Steps</h3>
                <ol>
                    {next_steps_list}
                </ol>
            </div>

            <div class="test-results">
                {test_results_cards}
            </div>

            <div class="charts-section">
                <h2>Performance Analysis Charts</h2>
                <div class="chart-grid">
                    {charts_html}
                </div>
            </div>

            <div class="recommendations">
                <h2>Actionable Recommendations</h2>
                {recommendations_html}
            </div>
        </div>

        <div class="footer">
            <p>Generated by Marty Framework Performance Analysis Suite</p>
            <p>Report ID: {report_id} | {generation_time}</p>
        </div>
    </div>
</body>
</html>
        """

        # Prepare template variables
        exec_summary = comprehensive_report["executive_summary"]
        generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Format critical issues
        critical_issues_html = ""
        if exec_summary["critical_issues_count"] > 0:
            critical_issues_html = f"""
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; padding: 15px; margin: 20px 0;">
                    <h4 style="color: #721c24; margin-top: 0;">⚠️ {exec_summary["critical_issues_count"]} Critical Issues Detected</h4>
                    <p>Immediate attention required for optimal system performance.</p>
                </div>
            """

        # Format key findings
        key_findings_html = "\\n".join(
            [f"<li>{finding}</li>" for finding in exec_summary.get("key_findings", [])]
        )

        # Format next steps
        next_steps_html = "\\n".join(
            [f"<li>{step}</li>" for step in exec_summary.get("recommended_next_steps", [])]
        )

        # Format test result cards
        test_results_html = ""
        for test_name, results in comprehensive_report["test_results_summary"].items():
            status = results.get("status", "unknown")
            status_class = "status-good" if status == "completed" else "status-needs_attention"

            test_results_html += f"""
                <div class="test-card">
                    <h3>{test_name.replace("_", " ").title()}</h3>
                    <span class="status-badge {status_class}">{status}</span>
                    <div style="margin-top: 15px;">
                        {self._format_test_details(results)}
                    </div>
                </div>
            """

        # Format charts
        charts_html = ""
        charts = comprehensive_report.get("charts_generated", {})
        for chart_name, chart_path in charts.items():
            chart_filename = Path(chart_path).name
            charts_html += f"""
                <div class="chart-item">
                    <h4>{chart_name.replace("_", " ").title()}</h4>
                    <img src="charts/{chart_filename}" alt="{chart_name}">
                </div>
            """

        # Format recommendations
        recommendations_html = ""
        recommendations = comprehensive_report.get("actionable_recommendations", [])
        for rec in recommendations:
            priority = rec.get("priority", "medium")
            recommendations_html += f"""
                <div class="recommendation-item priority-{priority}">
                    <h4>{rec.get("category", "General")}
                        <span class="status-badge status-{priority}">{priority}</span>
                    </h4>
                    <ul>
                        {"".join([f"<li>{action}</li>" for action in rec.get("actions", [])])}
                    </ul>
                    <small><em>Sources: {", ".join(rec.get("sources", []))}</em></small>
                </div>
            """

        # Fill template
        html_content = html_template.format(
            generation_time=generation_time,
            overall_score=int(exec_summary["overall_health_score"]),
            score_percentage=exec_summary["overall_health_score"],
            status=exec_summary["status"],
            status_message=exec_summary["status_message"],
            critical_issues_section=critical_issues_html,
            key_findings_list=key_findings_html,
            next_steps_list=next_steps_html,
            test_results_cards=test_results_html,
            charts_html=charts_html,
            recommendations_html=recommendations_html,
            report_id=str(hash(generation_time))[:8],
        )

        return html_content

    def _format_test_details(self, results):
        """Format test details for HTML display."""
        if results.get("status") == "not_run":
            return "<p><em>Test was not executed</em></p>"

        details = []
        for key, value in results.items():
            if key != "status" and key != "summary":
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, int | float):
                    details.append(f"<strong>{formatted_key}:</strong> {value}")
                elif isinstance(value, list):
                    details.append(f"<strong>{formatted_key}:</strong> {len(value)} items")
                else:
                    details.append(f"<strong>{formatted_key}:</strong> {value}")

        return "<br>".join(details) if details else "<p>No additional details available</p>"


# Integration test function
async def generate_comprehensive_performance_report(
    test_report_dir: Path,
    bottleneck_report: builtins.dict | None = None,
    timeout_report: builtins.dict | None = None,
    audit_report: builtins.dict | None = None,
    visual_report: builtins.dict | None = None,
) -> builtins.dict:
    """
    Generate comprehensive performance report combining all test results.

    Args:
        test_report_dir: Directory to save reports and charts
        bottleneck_report: Results from bottleneck analysis test
        timeout_report: Results from timeout detection test
        audit_report: Results from auditability test
        visual_report: Results from Playwright visual test

    Returns:
        Comprehensive report dictionary
    """

    generator = PerformanceReportGenerator(test_report_dir)

    return await generator.generate_comprehensive_report(
        bottleneck_report or {},
        timeout_report or {},
        audit_report or {},
        visual_report or {},
    )
