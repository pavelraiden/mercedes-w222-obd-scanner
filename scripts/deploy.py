#!/usr/bin/env python3
"""
Automated Deployment Script for Mercedes W222 OBD Scanner
Production-ready deployment automation with health checks and rollback
"""

import os
import sys
import json
import time
import subprocess
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DeploymentError(Exception):
    """Custom deployment error"""
    pass

class HealthChecker:
    """Health check utilities"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        
    def check_health(self) -> bool:
        """Check application health"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
            
    def check_api_endpoints(self) -> Dict[str, bool]:
        """Check critical API endpoints"""
        endpoints = [
            "/health",
            "/api/user/profile",  # Requires auth, but should return 401, not 500
        ]
        
        results = {}
        for endpoint in endpoints:
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    timeout=self.timeout
                )
                # For protected endpoints, 401 is acceptable
                results[endpoint] = response.status_code in [200, 401]
            except Exception as e:
                logger.error(f"Endpoint {endpoint} check failed: {e}")
                results[endpoint] = False
                
        return results
        
    def wait_for_health(self, max_attempts: int = 30, delay: int = 10) -> bool:
        """Wait for application to become healthy"""
        for attempt in range(max_attempts):
            if self.check_health():
                logger.info(f"Application healthy after {attempt + 1} attempts")
                return True
                
            logger.info(f"Health check attempt {attempt + 1}/{max_attempts} failed, waiting {delay}s...")
            time.sleep(delay)
            
        return False

class DockerDeployer:
    """Docker-based deployment"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_name = config.get('project_name', 'mercedes-obd-scanner')
        self.compose_file = config.get('compose_file', 'docker-compose.production.yml')
        
    def deploy(self) -> bool:
        """Deploy using Docker Compose"""
        try:
            logger.info("Starting Docker deployment...")
            
            # Pull latest images
            self._run_command([
                'docker-compose', '-f', self.compose_file,
                'pull'
            ])
            
            # Stop existing containers
            self._run_command([
                'docker-compose', '-f', self.compose_file,
                'down'
            ])
            
            # Start new containers
            self._run_command([
                'docker-compose', '-f', self.compose_file,
                'up', '-d'
            ])
            
            logger.info("Docker deployment completed")
            return True
            
        except Exception as e:
            logger.error(f"Docker deployment failed: {e}")
            return False
            
    def rollback(self, previous_version: str) -> bool:
        """Rollback to previous version"""
        try:
            logger.info(f"Rolling back to version {previous_version}...")
            
            # Update image tags to previous version
            env_vars = {
                'IMAGE_TAG': previous_version
            }
            
            # Deploy previous version
            cmd = ['docker-compose', '-f', self.compose_file, 'up', '-d']
            self._run_command(cmd, env_vars)
            
            logger.info("Rollback completed")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
            
    def _run_command(self, cmd: List[str], env_vars: Dict[str, str] = None):
        """Run shell command"""
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
            
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise DeploymentError(f"Command failed: {result.stderr}")
            
        return result.stdout

class DatabaseMigrator:
    """Database migration utilities"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    def backup_database(self) -> str:
        """Create database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_mercedes_obd_{timestamp}.sql"
        
        try:
            # For SQLite, just copy the file
            db_path = self.config.get('database_path', 'data/mercedes_obd_scanner.db')
            backup_path = f"backups/{backup_file}"
            
            os.makedirs('backups', exist_ok=True)
            
            if os.path.exists(db_path):
                import shutil
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backup created: {backup_path}")
                return backup_path
            else:
                logger.warning(f"Database file not found: {db_path}")
                return ""
                
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise DeploymentError(f"Database backup failed: {e}")
            
    def run_migrations(self) -> bool:
        """Run database migrations"""
        try:
            logger.info("Running database migrations...")
            
            # Initialize database manager to ensure tables exist
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from mercedes_obd_scanner.data.database_manager import DatabaseManager
            
            db_manager = DatabaseManager()
            logger.info("Database migrations completed")
            return True
            
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            return False
            
    def restore_database(self, backup_file: str) -> bool:
        """Restore database from backup"""
        try:
            logger.info(f"Restoring database from {backup_file}...")
            
            db_path = self.config.get('database_path', 'data/mercedes_obd_scanner.db')
            
            if os.path.exists(backup_file):
                import shutil
                shutil.copy2(backup_file, db_path)
                logger.info("Database restored successfully")
                return True
            else:
                logger.error(f"Backup file not found: {backup_file}")
                return False
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False

class ConfigManager:
    """Configuration management"""
    
    def __init__(self, config_file: str = "deployment.yml"):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load deployment configuration"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default configuration
            return {
                'project_name': 'mercedes-obd-scanner',
                'compose_file': 'docker-compose.production.yml',
                'health_check_url': 'http://localhost:8000',
                'database_path': 'data/mercedes_obd_scanner.db',
                'backup_retention_days': 7,
                'deployment_timeout': 300,
                'rollback_on_failure': True
            }
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
        
    def update_version(self, version: str):
        """Update deployed version in config"""
        self.config['current_version'] = version
        self.config['last_deployment'] = datetime.now().isoformat()
        
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)

class DeploymentManager:
    """Main deployment orchestrator"""
    
    def __init__(self, environment: str = "production"):
        self.environment = environment
        self.config = ConfigManager()
        self.docker_deployer = DockerDeployer(self.config.config)
        self.db_migrator = DatabaseMigrator(self.config.config)
        self.health_checker = HealthChecker(
            self.config.get('health_check_url', 'http://localhost:8000')
        )
        
    def deploy(self, version: str = None, skip_backup: bool = False) -> bool:
        """Execute full deployment"""
        deployment_start = datetime.now()
        backup_file = None
        
        try:
            logger.info(f"Starting deployment to {self.environment}")
            logger.info(f"Version: {version or 'latest'}")
            
            # Pre-deployment checks
            if not self._pre_deployment_checks():
                raise DeploymentError("Pre-deployment checks failed")
                
            # Create database backup
            if not skip_backup:
                backup_file = self.db_migrator.backup_database()
                
            # Run database migrations
            if not self.db_migrator.run_migrations():
                raise DeploymentError("Database migrations failed")
                
            # Deploy application
            if not self.docker_deployer.deploy():
                raise DeploymentError("Application deployment failed")
                
            # Wait for application to be healthy
            if not self.health_checker.wait_for_health():
                raise DeploymentError("Application failed health checks")
                
            # Post-deployment verification
            if not self._post_deployment_checks():
                raise DeploymentError("Post-deployment checks failed")
                
            # Update configuration
            if version:
                self.config.update_version(version)
                
            deployment_time = (datetime.now() - deployment_start).total_seconds()
            logger.info(f"Deployment completed successfully in {deployment_time:.1f}s")
            
            # Clean up old backups
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            
            # Rollback if configured
            if self.config.get('rollback_on_failure', True):
                self._rollback(backup_file)
                
            return False
            
    def _pre_deployment_checks(self) -> bool:
        """Run pre-deployment checks"""
        logger.info("Running pre-deployment checks...")
        
        checks = [
            self._check_docker_availability,
            self._check_disk_space,
            self._check_required_files
        ]
        
        for check in checks:
            if not check():
                return False
                
        logger.info("Pre-deployment checks passed")
        return True
        
    def _post_deployment_checks(self) -> bool:
        """Run post-deployment checks"""
        logger.info("Running post-deployment checks...")
        
        # Check API endpoints
        endpoint_results = self.health_checker.check_api_endpoints()
        
        failed_endpoints = [ep for ep, status in endpoint_results.items() if not status]
        if failed_endpoints:
            logger.error(f"Failed endpoints: {failed_endpoints}")
            return False
            
        logger.info("Post-deployment checks passed")
        return True
        
    def _check_docker_availability(self) -> bool:
        """Check if Docker is available"""
        try:
            subprocess.run(['docker', '--version'], capture_output=True, check=True)
            subprocess.run(['docker-compose', '--version'], capture_output=True, check=True)
            return True
        except Exception as e:
            logger.error(f"Docker not available: {e}")
            return False
            
    def _check_disk_space(self) -> bool:
        """Check available disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage('.')
            free_gb = free / (1024**3)
            
            if free_gb < 1.0:  # Less than 1GB free
                logger.error(f"Insufficient disk space: {free_gb:.1f}GB free")
                return False
                
            logger.info(f"Disk space check passed: {free_gb:.1f}GB free")
            return True
            
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return False
            
    def _check_required_files(self) -> bool:
        """Check if required files exist"""
        required_files = [
            self.config.get('compose_file', 'docker-compose.production.yml'),
            'Dockerfile.production'
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                logger.error(f"Required file missing: {file_path}")
                return False
                
        logger.info("Required files check passed")
        return True
        
    def _rollback(self, backup_file: str = None):
        """Rollback deployment"""
        logger.info("Starting rollback...")
        
        try:
            # Get previous version
            previous_version = self.config.get('previous_version', 'latest')
            
            # Rollback application
            if self.docker_deployer.rollback(previous_version):
                logger.info("Application rollback completed")
                
            # Restore database if backup exists
            if backup_file and os.path.exists(backup_file):
                if self.db_migrator.restore_database(backup_file):
                    logger.info("Database rollback completed")
                    
            # Wait for health
            if self.health_checker.wait_for_health():
                logger.info("Rollback successful - application is healthy")
            else:
                logger.error("Rollback completed but application is not healthy")
                
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            
    def _cleanup_old_backups(self):
        """Clean up old backup files"""
        try:
            retention_days = self.config.get('backup_retention_days', 7)
            backup_dir = Path('backups')
            
            if not backup_dir.exists():
                return
                
            cutoff_time = time.time() - (retention_days * 24 * 3600)
            
            for backup_file in backup_dir.glob('backup_mercedes_obd_*.sql'):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    logger.info(f"Deleted old backup: {backup_file}")
                    
        except Exception as e:
            logger.warning(f"Backup cleanup failed: {e}")

def main():
    """Main deployment script"""
    parser = argparse.ArgumentParser(description='Mercedes W222 OBD Scanner Deployment')
    parser.add_argument('--environment', '-e', default='production',
                       help='Deployment environment')
    parser.add_argument('--version', '-v', help='Version to deploy')
    parser.add_argument('--skip-backup', action='store_true',
                       help='Skip database backup')
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform dry run without actual deployment')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No actual deployment will be performed")
        return True
        
    # Create deployment manager
    deployment_manager = DeploymentManager(args.environment)
    
    # Execute deployment
    success = deployment_manager.deploy(
        version=args.version,
        skip_backup=args.skip_backup
    )
    
    if success:
        logger.info("🎉 Deployment completed successfully!")
        return True
    else:
        logger.error("❌ Deployment failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
