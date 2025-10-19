#!/usr/bin/env python3
"""
Security Audit Tool for Microservices Framework

Performs comprehensive security audits including:
- Code security analysis
- Dependency vulnerability scanning
- Configuration security review
- Container security assessment
- Infrastructure security validation
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SecurityAuditTool:
    """Main security audit tool"""

    def __init__(self, project_root: Path, output_dir: Path | None = None):
        self.project_root = project_root
        self.output_dir = output_dir or project_root / "reports" / "security"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize results storage
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(project_root),
            "audit_results": {
                "code_security": {},
                "dependencies": {},
                "containers": {},
                "configurations": {},
                "infrastructure": {},
                "summary": {},
            },
        }

    def run_full_audit(self) -> dict:
        """Run complete security audit"""
        logger.info("Starting comprehensive security audit...")

        try:
            # 1. Code security analysis
            logger.info("Running code security analysis...")
            self.results["audit_results"]["code_security"] = self._audit_code_security()

            # 2. Dependency vulnerability scanning
            logger.info("Scanning dependencies for vulnerabilities...")
            self.results["audit_results"]["dependencies"] = self._audit_dependencies()

            # 3. Container security assessment
            logger.info("Assessing container security...")
            self.results["audit_results"]["containers"] = self._audit_containers()

            # 4. Configuration security review
            logger.info("Reviewing configuration security...")
            self.results["audit_results"]["configurations"] = self._audit_configurations()

            # 5. Infrastructure security validation
            logger.info("Validating infrastructure security...")
            self.results["audit_results"]["infrastructure"] = self._audit_infrastructure()

            # 6. Generate summary
            logger.info("Generating audit summary...")
            self.results["audit_results"]["summary"] = self._generate_summary()

            # Save results
            self._save_results()

            logger.info("Security audit completed successfully!")
            return self.results

        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            raise

    def _audit_code_security(self) -> dict:
        """Audit code security using multiple tools"""
        results = {
            "bandit": {},
            "semgrep": {},
            "custom_checks": {},
            "issues_found": 0,
            "critical_issues": 0,
        }

        try:
            # Run Bandit analysis
            bandit_results = self._run_bandit()
            results["bandit"] = bandit_results

            # Run Semgrep analysis (if available)
            semgrep_results = self._run_semgrep()
            results["semgrep"] = semgrep_results

            # Run custom security checks
            custom_results = self._run_custom_security_checks()
            results["custom_checks"] = custom_results

            # Count issues
            results["issues_found"] = (
                bandit_results.get("issues_count", 0)
                + semgrep_results.get("issues_count", 0)
                + custom_results.get("issues_count", 0)
            )

            results["critical_issues"] = (
                bandit_results.get("critical_count", 0)
                + semgrep_results.get("critical_count", 0)
                + custom_results.get("critical_count", 0)
            )

        except Exception as e:
            logger.error(f"Code security audit failed: {e}")
            results["error"] = str(e)

        return results

    def _run_bandit(self) -> dict:
        """Run Bandit security analysis"""
        try:
            cmd = [
                "bandit",
                "-r",
                str(self.project_root),
                "-f",
                "json",
                "-o",
                str(self.output_dir / "bandit_results.json"),
            ]

            # Exclude common non-security paths
            excludes = [
                "*/tests/*",
                "*/test_*",
                "*/.venv/*",
                "*/venv/*",
                "*/__pycache__/*",
            ]

            for exclude in excludes:
                cmd.extend(["-x", exclude])

            subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Parse results
            results_file = self.output_dir / "bandit_results.json"
            if results_file.exists():
                with open(results_file) as f:
                    bandit_data = json.load(f)

                return {
                    "status": "completed",
                    "issues_count": len(bandit_data.get("results", [])),
                    "critical_count": len(
                        [
                            r
                            for r in bandit_data.get("results", [])
                            if r.get("issue_severity") == "HIGH"
                        ]
                    ),
                    "results_file": str(results_file),
                }
            return {"status": "failed", "error": "No results file generated"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_semgrep(self) -> dict:
        """Run Semgrep analysis"""
        try:
            # Check if semgrep is available
            result = subprocess.run(["semgrep", "--version"], capture_output=True, check=False)
            if result.returncode != 0:
                return {"status": "skipped", "reason": "Semgrep not available"}

            cmd = [
                "semgrep",
                "--config=auto",
                "--json",
                "--output",
                str(self.output_dir / "semgrep_results.json"),
                str(self.project_root),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Parse results
            results_file = self.output_dir / "semgrep_results.json"
            if results_file.exists():
                with open(results_file) as f:
                    semgrep_data = json.load(f)

                return {
                    "status": "completed",
                    "issues_count": len(semgrep_data.get("results", [])),
                    "critical_count": len(
                        [
                            r
                            for r in semgrep_data.get("results", [])
                            if r.get("extra", {}).get("severity") == "ERROR"
                        ]
                    ),
                    "results_file": str(results_file),
                }
            return {"status": "failed", "error": "No results file generated"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_custom_security_checks(self) -> dict:
        """Run custom security checks specific to microservices"""
        issues = []

        try:
            # Check for hardcoded secrets
            secret_patterns = [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']',
            ]

            for pattern in secret_patterns:
                issues.extend(self._find_pattern_in_files(pattern, "Potential hardcoded secret"))

            # Check for insecure configurations
            insecure_patterns = [
                (r"ssl_verify\s*=\s*False", "SSL verification disabled"),
                (r"verify\s*=\s*False", "Certificate verification disabled"),
                (r"debug\s*=\s*True", "Debug mode enabled"),
                (r'CORS\(.*origins=\["?\*"?\]', "CORS allows all origins"),
            ]

            for pattern, description in insecure_patterns:
                issues.extend(self._find_pattern_in_files(pattern, description))

            # Check for missing security headers
            self._check_security_headers_implementation(issues)

            # Check for proper input validation
            self._check_input_validation(issues)

            return {
                "status": "completed",
                "issues_count": len(issues),
                "critical_count": len([i for i in issues if i.get("severity") == "critical"]),
                "issues": issues,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _find_pattern_in_files(self, pattern: str, description: str) -> list[dict]:
        """Find pattern in Python files"""

        issues = []

        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    matches = re.finditer(pattern, content, re.IGNORECASE)

                    for match in matches:
                        line_num = content[: match.start()].count("\n") + 1
                        issues.append(
                            {
                                "file": str(py_file.relative_to(self.project_root)),
                                "line": line_num,
                                "pattern": pattern,
                                "description": description,
                                "severity": "medium",
                                "match": match.group(),
                            }
                        )
            except Exception as e:
                logger.warning(f"Error reading file {py_file}: {e}")

        return issues

    def _check_security_headers_implementation(self, issues: list[dict]):
        """Check if security headers are properly implemented"""
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Strict-Transport-Security",
            "Content-Security-Policy",
        ]

        # Look for security headers middleware
        middleware_found = False
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    if any(header in content for header in security_headers):
                        middleware_found = True
                        break
            except Exception:
                continue

        if not middleware_found:
            issues.append(
                {
                    "file": "global",
                    "line": 0,
                    "description": "Security headers middleware not implemented",
                    "severity": "high",
                    "recommendation": "Implement security headers middleware",
                }
            )

    def _check_input_validation(self, issues: list[dict]):
        """Check for proper input validation implementation"""
        validation_patterns = [
            "pydantic",
            "BaseModel",
            "validator",
            "Field",
            "@validate_arguments",
        ]

        validation_found = False
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    if any(pattern in content for pattern in validation_patterns):
                        validation_found = True
                        break
            except Exception:
                continue

        if not validation_found:
            issues.append(
                {
                    "file": "global",
                    "line": 0,
                    "description": "Input validation framework not detected",
                    "severity": "medium",
                    "recommendation": "Implement Pydantic models for input validation",
                }
            )

    def _audit_dependencies(self) -> dict:
        """Audit dependencies for vulnerabilities"""
        results = {
            "safety": {},
            "pip_audit": {},
            "outdated_packages": {},
            "total_vulnerabilities": 0,
        }

        try:
            # Run safety check
            safety_results = self._run_safety_check()
            results["safety"] = safety_results

            # Run pip-audit if available
            pip_audit_results = self._run_pip_audit()
            results["pip_audit"] = pip_audit_results

            # Check for outdated packages
            outdated_results = self._check_outdated_packages()
            results["outdated_packages"] = outdated_results

            # Calculate total vulnerabilities
            results["total_vulnerabilities"] = safety_results.get(
                "vulnerabilities_count", 0
            ) + pip_audit_results.get("vulnerabilities_count", 0)

        except Exception as e:
            logger.error(f"Dependency audit failed: {e}")
            results["error"] = str(e)

        return results

    def _run_safety_check(self) -> dict:
        """Run safety vulnerability check"""
        try:
            cmd = [
                "safety",
                "check",
                "--json",
                "--output",
                str(self.output_dir / "safety_results.json"),
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Parse results
            results_file = self.output_dir / "safety_results.json"
            if results_file.exists():
                with open(results_file) as f:
                    safety_data = json.load(f)

                return {
                    "status": "completed",
                    "vulnerabilities_count": len(safety_data),
                    "results_file": str(results_file),
                }
            return {"status": "failed", "error": "No results file generated"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_pip_audit(self) -> dict:
        """Run pip-audit vulnerability check"""
        try:
            # Check if pip-audit is available
            result = subprocess.run(["pip-audit", "--version"], capture_output=True, check=False)
            if result.returncode != 0:
                return {"status": "skipped", "reason": "pip-audit not available"}

            cmd = [
                "pip-audit",
                "--format=json",
                "--output",
                str(self.output_dir / "pip_audit_results.json"),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            # Parse results
            results_file = self.output_dir / "pip_audit_results.json"
            if results_file.exists():
                with open(results_file) as f:
                    audit_data = json.load(f)

                return {
                    "status": "completed",
                    "vulnerabilities_count": len(audit_data.get("vulnerabilities", [])),
                    "results_file": str(results_file),
                }
            return {"status": "failed", "error": "No results file generated"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_outdated_packages(self) -> dict:
        """Check for outdated packages"""
        try:
            cmd = ["pip", "list", "--outdated", "--format=json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                outdated_data = json.loads(result.stdout)

                # Save results
                results_file = self.output_dir / "outdated_packages.json"
                with open(results_file, "w") as f:
                    json.dump(outdated_data, f, indent=2)

                return {
                    "status": "completed",
                    "outdated_count": len(outdated_data),
                    "results_file": str(results_file),
                }
            return {"status": "failed", "error": result.stderr}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _audit_containers(self) -> dict:
        """Audit container security"""
        results = {
            "dockerfile_analysis": {},
            "image_scanning": {},
            "security_best_practices": {},
        }

        try:
            # Analyze Dockerfiles
            dockerfile_results = self._analyze_dockerfiles()
            results["dockerfile_analysis"] = dockerfile_results

            # Check security best practices
            best_practices_results = self._check_container_best_practices()
            results["security_best_practices"] = best_practices_results

        except Exception as e:
            logger.error(f"Container audit failed: {e}")
            results["error"] = str(e)

        return results

    def _analyze_dockerfiles(self) -> dict:
        """Analyze Dockerfiles for security issues"""
        issues = []
        dockerfiles = list(self.project_root.rglob("*Dockerfile*"))

        for dockerfile in dockerfiles:
            try:
                with open(dockerfile) as f:
                    content = f.read()
                    file_issues = self._check_dockerfile_security(dockerfile, content)
                    issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"Error analyzing {dockerfile}: {e}")

        return {
            "dockerfiles_analyzed": len(dockerfiles),
            "issues_found": len(issues),
            "issues": issues,
        }

    def _check_dockerfile_security(self, dockerfile: Path, content: str) -> list[dict]:
        """Check individual Dockerfile for security issues"""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Check for root user
            if line.upper().startswith("USER") and "root" in line.lower():
                issues.append(
                    {
                        "file": str(dockerfile.relative_to(self.project_root)),
                        "line": i,
                        "issue": "Running as root user",
                        "severity": "high",
                        "recommendation": "Use non-root user",
                    }
                )

            # Check for latest tag
            if line.upper().startswith("FROM") and ":latest" in line:
                issues.append(
                    {
                        "file": str(dockerfile.relative_to(self.project_root)),
                        "line": i,
                        "issue": "Using 'latest' tag",
                        "severity": "medium",
                        "recommendation": "Pin specific version",
                    }
                )

            # Check for ADD vs COPY
            if line.upper().startswith("ADD") and not line.lower().startswith("add --"):
                issues.append(
                    {
                        "file": str(dockerfile.relative_to(self.project_root)),
                        "line": i,
                        "issue": "Using ADD instead of COPY",
                        "severity": "low",
                        "recommendation": "Use COPY for local files",
                    }
                )

            # Check for missing health check
            if i == len(lines) and not any("HEALTHCHECK" in line for line in lines):
                issues.append(
                    {
                        "file": str(dockerfile.relative_to(self.project_root)),
                        "line": i,
                        "issue": "Missing HEALTHCHECK instruction",
                        "severity": "medium",
                        "recommendation": "Add HEALTHCHECK instruction",
                    }
                )

        return issues

    def _check_container_best_practices(self) -> dict:
        """Check container security best practices"""
        # This would integrate with tools like:
        # - Docker Bench Security
        # - Clair
        # - Trivy
        # For now, return placeholder
        return {
            "status": "completed",
            "note": "Container security scanning requires additional tools like Trivy or Clair",
        }

    def _audit_configurations(self) -> dict:
        """Audit configuration security"""
        results = {
            "kubernetes_configs": {},
            "application_configs": {},
            "secrets_management": {},
        }

        try:
            # Audit Kubernetes configurations
            k8s_results = self._audit_kubernetes_configs()
            results["kubernetes_configs"] = k8s_results

            # Audit application configurations
            app_results = self._audit_application_configs()
            results["application_configs"] = app_results

            # Check secrets management
            secrets_results = self._audit_secrets_management()
            results["secrets_management"] = secrets_results

        except Exception as e:
            logger.error(f"Configuration audit failed: {e}")
            results["error"] = str(e)

        return results

    def _audit_kubernetes_configs(self) -> dict:
        """Audit Kubernetes configuration files"""
        issues = []
        k8s_files = []

        # Find Kubernetes YAML files
        for yaml_file in self.project_root.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict) and content.get("apiVersion"):
                        k8s_files.append(yaml_file)
                        file_issues = self._check_k8s_security(yaml_file, content)
                        issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"Error analyzing {yaml_file}: {e}")

        return {
            "files_analyzed": len(k8s_files),
            "issues_found": len(issues),
            "issues": issues,
        }

    def _check_k8s_security(self, yaml_file: Path, content: dict) -> list[dict]:
        """Check Kubernetes YAML for security issues"""
        issues = []

        # Check for missing security context
        if content.get("kind") == "Pod" or content.get("kind") == "Deployment":
            spec = content.get("spec", {})
            if content.get("kind") == "Deployment":
                spec = spec.get("template", {}).get("spec", {})

            if not spec.get("securityContext"):
                issues.append(
                    {
                        "file": str(yaml_file.relative_to(self.project_root)),
                        "issue": "Missing securityContext",
                        "severity": "high",
                        "recommendation": "Add securityContext with runAsNonRoot: true",
                    }
                )

            # Check containers
            for container in spec.get("containers", []):
                if not container.get("securityContext"):
                    issues.append(
                        {
                            "file": str(yaml_file.relative_to(self.project_root)),
                            "issue": f"Container {container.get('name')} missing securityContext",
                            "severity": "high",
                            "recommendation": "Add container securityContext",
                        }
                    )

                # Check for privileged containers
                security_context = container.get("securityContext", {})
                if security_context.get("privileged"):
                    issues.append(
                        {
                            "file": str(yaml_file.relative_to(self.project_root)),
                            "issue": f"Container {container.get('name')} is privileged",
                            "severity": "critical",
                            "recommendation": "Remove privileged: true",
                        }
                    )

        return issues

    def _audit_application_configs(self) -> dict:
        """Audit application configuration files"""
        issues = []
        config_files = []

        # Find configuration files
        for config_file in self.project_root.rglob("*.yaml"):
            if "config" in str(config_file).lower():
                config_files.append(config_file)

        for config_file in self.project_root.rglob("*.json"):
            if "config" in str(config_file).lower():
                config_files.append(config_file)

        for config_file in config_files:
            try:
                file_issues = self._check_config_security(config_file)
                issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"Error analyzing {config_file}: {e}")

        return {
            "files_analyzed": len(config_files),
            "issues_found": len(issues),
            "issues": issues,
        }

    def _check_config_security(self, config_file: Path) -> list[dict]:
        """Check configuration file for security issues"""
        issues = []

        try:
            with open(config_file) as f:
                content = f.read()

                # Check for hardcoded secrets
                secret_patterns = ["password", "secret", "key", "token", "credential"]

                for pattern in secret_patterns:
                    if pattern in content.lower() and "=" in content:
                        issues.append(
                            {
                                "file": str(config_file.relative_to(self.project_root)),
                                "issue": f"Potential hardcoded {pattern}",
                                "severity": "high",
                                "recommendation": "Use environment variables or secret management",
                            }
                        )

        except Exception as e:
            logger.warning(f"Error reading {config_file}: {e}")

        return issues

    def _audit_secrets_management(self) -> dict:
        """Audit secrets management practices"""
        issues = []

        # Check for .env files
        env_files = list(self.project_root.rglob("*.env*"))
        if env_files:
            issues.append(
                {
                    "issue": f"Found {len(env_files)} .env files",
                    "severity": "medium",
                    "recommendation": "Ensure .env files are not committed to version control",
                    "files": [str(f.relative_to(self.project_root)) for f in env_files],
                }
            )

        # Check for secrets in code
        secret_files = []
        for py_file in self.project_root.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read()
                    if any(pattern in content.lower() for pattern in ["getenv", "environ"]):
                        secret_files.append(py_file)
            except Exception:
                continue

        return {
            "env_files_found": len(env_files),
            "secret_management_files": len(secret_files),
            "issues": issues,
            "recommendation": "Use proper secret management like Kubernetes secrets or HashiCorp Vault",
        }

    def _audit_infrastructure(self) -> dict:
        """Audit infrastructure security"""
        results = {"network_policies": {}, "rbac": {}, "ingress_security": {}}

        try:
            # Check for network policies
            network_results = self._check_network_policies()
            results["network_policies"] = network_results

            # Check RBAC configurations
            rbac_results = self._check_rbac_configs()
            results["rbac"] = rbac_results

            # Check ingress security
            ingress_results = self._check_ingress_security()
            results["ingress_security"] = ingress_results

        except Exception as e:
            logger.error(f"Infrastructure audit failed: {e}")
            results["error"] = str(e)

        return results

    def _check_network_policies(self) -> dict:
        """Check for network policy implementations"""
        network_policies = []

        for yaml_file in self.project_root.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict) and content.get("kind") == "NetworkPolicy":
                        network_policies.append(yaml_file)
            except Exception:
                continue

        return {
            "network_policies_found": len(network_policies),
            "files": [str(f.relative_to(self.project_root)) for f in network_policies],
            "recommendation": "Implement network policies to restrict pod-to-pod communication"
            if not network_policies
            else "Network policies found",
        }

    def _check_rbac_configs(self) -> dict:
        """Check RBAC configurations"""
        rbac_files = []

        for yaml_file in self.project_root.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict) and content.get("kind") in [
                        "Role",
                        "RoleBinding",
                        "ClusterRole",
                        "ClusterRoleBinding",
                    ]:
                        rbac_files.append(yaml_file)
            except Exception:
                continue

        return {
            "rbac_files_found": len(rbac_files),
            "files": [str(f.relative_to(self.project_root)) for f in rbac_files],
            "recommendation": "Implement proper RBAC with least privilege principle",
        }

    def _check_ingress_security(self) -> dict:
        """Check ingress security configurations"""
        ingress_files = []
        security_annotations = []

        for yaml_file in self.project_root.rglob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    content = yaml.safe_load(f)
                    if isinstance(content, dict) and content.get("kind") == "Ingress":
                        ingress_files.append(yaml_file)

                        # Check for security annotations
                        annotations = content.get("metadata", {}).get("annotations", {})
                        security_keys = [
                            k
                            for k in annotations.keys()
                            if any(sec in k for sec in ["ssl", "tls", "rate-limit", "auth"])
                        ]
                        security_annotations.extend(security_keys)
            except Exception:
                continue

        return {
            "ingress_files_found": len(ingress_files),
            "security_annotations_found": len(security_annotations),
            "files": [str(f.relative_to(self.project_root)) for f in ingress_files],
            "recommendation": "Add security annotations to ingress resources (SSL, rate limiting, etc.)",
        }

    def _generate_summary(self) -> dict:
        """Generate audit summary"""
        audit_results = self.results["audit_results"]

        # Count total issues
        total_issues = 0
        critical_issues = 0

        for category, results in audit_results.items():
            if category == "summary":
                continue

            if isinstance(results, dict):
                total_issues += results.get("issues_found", 0)
                critical_issues += results.get("critical_issues", 0)
                total_issues += results.get("total_vulnerabilities", 0)

        # Determine overall security score
        if critical_issues > 5:
            security_score = "POOR"
        elif critical_issues > 0 or total_issues > 20:
            security_score = "FAIR"
        elif total_issues > 5:
            security_score = "GOOD"
        else:
            security_score = "EXCELLENT"

        return {
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "security_score": security_score,
            "recommendations": [
                "Address all critical security issues immediately",
                "Implement security middleware for all services",
                "Use proper secret management",
                "Add network policies and RBAC",
                "Regular security scanning in CI/CD",
                "Container security best practices",
            ],
        }

    def _save_results(self):
        """Save audit results to file"""
        results_file = self.output_dir / "security_audit_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Audit results saved to {results_file}")

        # Generate markdown report
        self._generate_markdown_report()

    def _generate_markdown_report(self):
        """Generate markdown report"""
        report_file = self.output_dir / "security_audit_report.md"

        with open(report_file, "w") as f:
            f.write("# Security Audit Report\n\n")
            f.write(f"**Generated:** {self.results['timestamp']}\n\n")
            f.write(f"**Project:** {self.results['project_root']}\n\n")

            summary = self.results["audit_results"]["summary"]
            f.write("## Summary\n\n")
            f.write(f"- **Security Score:** {summary['security_score']}\n")
            f.write(f"- **Total Issues:** {summary['total_issues']}\n")
            f.write(f"- **Critical Issues:** {summary['critical_issues']}\n\n")

            f.write("## Recommendations\n\n")
            for rec in summary["recommendations"]:
                f.write(f"- {rec}\n")

            f.write("\n## Detailed Results\n\n")

            for category, results in self.results["audit_results"].items():
                if category != "summary":
                    f.write(f"### {category.replace('_', ' ').title()}\n\n")
                    f.write(f"```json\n{json.dumps(results, indent=2)}\n```\n\n")

        logger.info(f"Markdown report saved to {report_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Security Audit Tool for Microservices Framework")
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="Project root directory"
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        auditor = SecurityAuditTool(args.project_root, args.output_dir)
        results = auditor.run_full_audit()

        summary = results["audit_results"]["summary"]
        print("\n🛡️  Security Audit Complete!")
        print(f"Security Score: {summary['security_score']}")
        print(f"Total Issues: {summary['total_issues']}")
        print(f"Critical Issues: {summary['critical_issues']}")
        print(f"\nResults saved to: {auditor.output_dir}")

        # Exit with error code if critical issues found
        if summary["critical_issues"] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Security audit failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
