#!/usr/bin/env python3
"""
Disaster Recovery and Backup System for Mercedes W222 OBD Scanner
Enterprise-grade backup, restore, and disaster recovery capabilities
"""

import os
import json
import time
import shutil
import sqlite3
import logging
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import tarfile
import gzip
import hashlib
import boto3
from botocore.exceptions import ClientError
import schedule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BackupJob:
    """Backup job configuration"""
    job_id: str
    name: str
    source_paths: List[str]
    backup_type: str  # full, incremental, differential
    schedule: str  # cron-like schedule
    retention_days: int
    compression: bool
    encryption: bool
    destination: str  # local, s3, ftp
    enabled: bool
    last_run: Optional[datetime] = None
    last_status: str = "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'name': self.name,
            'source_paths': self.source_paths,
            'backup_type': self.backup_type,
            'schedule': self.schedule,
            'retention_days': self.retention_days,
            'compression': self.compression,
            'encryption': self.encryption,
            'destination': self.destination,
            'enabled': self.enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_status': self.last_status
        }

@dataclass
class BackupRecord:
    """Backup execution record"""
    backup_id: str
    job_id: str
    timestamp: datetime
    backup_type: str
    file_path: str
    file_size: int
    checksum: str
    status: str  # success, failed, partial
    duration_seconds: float
    files_backed_up: int
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'backup_id': self.backup_id,
            'job_id': self.job_id,
            'timestamp': self.timestamp.isoformat(),
            'backup_type': self.backup_type,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'checksum': self.checksum,
            'status': self.status,
            'duration_seconds': self.duration_seconds,
            'files_backed_up': self.files_backed_up,
            'errors': self.errors
        }

class DatabaseBackupManager:
    """Database backup and restore operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def backup_database(self, backup_path: str) -> bool:
        """Create database backup"""
        try:
            # Create backup directory
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # SQLite backup using .backup command
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup:
                    source.backup(backup)
            
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False
    
    def restore_database(self, backup_path: str, target_path: str = None) -> bool:
        """Restore database from backup"""
        try:
            if target_path is None:
                target_path = self.db_path
            
            # Create backup of current database
            current_backup = f"{target_path}.pre_restore_{int(time.time())}"
            if os.path.exists(target_path):
                shutil.copy2(target_path, current_backup)
                logger.info(f"Current database backed up to: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, target_path)
            
            # Verify restored database
            if self._verify_database(target_path):
                logger.info(f"Database restored successfully from: {backup_path}")
                return True
            else:
                # Restore original if verification failed
                if os.path.exists(current_backup):
                    shutil.copy2(current_backup, target_path)
                logger.error("Database verification failed, restored original")
                return False
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def _verify_database(self, db_path: str) -> bool:
        """Verify database integrity"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                return result == "ok"
        except Exception:
            return False
    
    def export_data(self, export_path: str, tables: List[str] = None) -> bool:
        """Export database data to JSON"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                export_data = {}
                
                # Get all tables if none specified
                if tables is None:
                    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                
                # Export each table
                for table in tables:
                    cursor = conn.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    export_data[table] = [dict(row) for row in rows]
                
                # Write to JSON file
                with open(export_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                logger.info(f"Data exported to: {export_path}")
                return True
                
        except Exception as e:
            logger.error(f"Data export failed: {e}")
            return False

class FileBackupManager:
    """File system backup operations"""
    
    def __init__(self):
        self.excluded_patterns = [
            '*.tmp', '*.log', '__pycache__', '.git',
            '*.pyc', '.DS_Store', 'Thumbs.db'
        ]
    
    def create_backup_archive(self, source_paths: List[str], backup_path: str,
                            compression: bool = True, encryption: bool = False) -> Dict[str, Any]:
        """Create backup archive from source paths"""
        start_time = time.time()
        files_backed_up = 0
        errors = []
        
        try:
            # Create backup directory
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Determine compression mode
            mode = 'w:gz' if compression else 'w'
            
            with tarfile.open(backup_path, mode) as tar:
                for source_path in source_paths:
                    if os.path.exists(source_path):
                        try:
                            if os.path.isfile(source_path):
                                tar.add(source_path, arcname=os.path.basename(source_path))
                                files_backed_up += 1
                            else:
                                # Add directory recursively
                                for root, dirs, files in os.walk(source_path):
                                    # Filter out excluded patterns
                                    dirs[:] = [d for d in dirs if not self._is_excluded(d)]
                                    
                                    for file in files:
                                        if not self._is_excluded(file):
                                            file_path = os.path.join(root, file)
                                            arcname = os.path.relpath(file_path, os.path.dirname(source_path))
                                            tar.add(file_path, arcname=arcname)
                                            files_backed_up += 1
                        except Exception as e:
                            error_msg = f"Failed to backup {source_path}: {e}"
                            errors.append(error_msg)
                            logger.warning(error_msg)
            
            # Calculate checksum
            checksum = self._calculate_file_checksum(backup_path)
            
            # Encrypt if requested
            if encryption:
                encrypted_path = f"{backup_path}.enc"
                if self._encrypt_file(backup_path, encrypted_path):
                    os.remove(backup_path)
                    backup_path = encrypted_path
                    checksum = self._calculate_file_checksum(backup_path)
            
            duration = time.time() - start_time
            file_size = os.path.getsize(backup_path)
            
            return {
                'success': True,
                'backup_path': backup_path,
                'file_size': file_size,
                'checksum': checksum,
                'duration_seconds': duration,
                'files_backed_up': files_backed_up,
                'errors': errors
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Backup creation failed: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return {
                'success': False,
                'backup_path': backup_path,
                'file_size': 0,
                'checksum': '',
                'duration_seconds': duration,
                'files_backed_up': files_backed_up,
                'errors': errors
            }
    
    def restore_from_archive(self, backup_path: str, restore_path: str,
                           encryption: bool = False) -> bool:
        """Restore files from backup archive"""
        try:
            # Decrypt if needed
            if encryption:
                decrypted_path = f"{backup_path}.dec"
                if not self._decrypt_file(backup_path, decrypted_path):
                    return False
                backup_path = decrypted_path
            
            # Extract archive
            with tarfile.open(backup_path, 'r:*') as tar:
                tar.extractall(restore_path)
            
            # Clean up decrypted file
            if encryption and os.path.exists(f"{backup_path}.dec"):
                os.remove(f"{backup_path}.dec")
            
            logger.info(f"Files restored to: {restore_path}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def _is_excluded(self, name: str) -> bool:
        """Check if file/directory should be excluded"""
        import fnmatch
        return any(fnmatch.fnmatch(name, pattern) for pattern in self.excluded_patterns)
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _encrypt_file(self, source_path: str, target_path: str) -> bool:
        """Encrypt file (simplified - use proper encryption in production)"""
        try:
            # In production, use proper encryption like AES
            # This is a simple XOR for demo purposes
            key = b"mercedes_obd_scanner_key_2024"
            
            with open(source_path, 'rb') as src, open(target_path, 'wb') as tgt:
                while True:
                    chunk = src.read(4096)
                    if not chunk:
                        break
                    
                    encrypted_chunk = bytes(a ^ b for a, b in zip(chunk, key * (len(chunk) // len(key) + 1)))
                    tgt.write(encrypted_chunk)
            
            return True
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return False
    
    def _decrypt_file(self, source_path: str, target_path: str) -> bool:
        """Decrypt file (simplified - use proper decryption in production)"""
        # Same as encryption for XOR
        return self._encrypt_file(source_path, target_path)

class CloudBackupManager:
    """Cloud backup operations (AWS S3)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.s3_client = None
        
        if config.get('aws', {}).get('enabled', False):
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=config['aws']['access_key_id'],
                    aws_secret_access_key=config['aws']['secret_access_key'],
                    region_name=config['aws'].get('region', 'us-east-1')
                )
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
    
    def upload_backup(self, local_path: str, s3_key: str) -> bool:
        """Upload backup to S3"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False
        
        try:
            bucket = self.config['aws']['bucket']
            
            # Upload with metadata
            extra_args = {
                'Metadata': {
                    'backup_timestamp': datetime.now().isoformat(),
                    'source_system': 'mercedes-obd-scanner'
                }
            }
            
            self.s3_client.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args)
            logger.info(f"Backup uploaded to S3: s3://{bucket}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return False
    
    def download_backup(self, s3_key: str, local_path: str) -> bool:
        """Download backup from S3"""
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return False
        
        try:
            bucket = self.config['aws']['bucket']
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.s3_client.download_file(bucket, s3_key, local_path)
            logger.info(f"Backup downloaded from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 download failed: {e}")
            return False
    
    def list_backups(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List backups in S3"""
        if not self.s3_client:
            return []
        
        try:
            bucket = self.config['aws']['bucket']
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            backups = []
            for obj in response.get('Contents', []):
                backups.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag']
                })
            
            return sorted(backups, key=lambda x: x['last_modified'], reverse=True)
            
        except ClientError as e:
            logger.error(f"Failed to list S3 backups: {e}")
            return []
    
    def delete_old_backups(self, prefix: str, retention_days: int) -> int:
        """Delete old backups from S3"""
        if not self.s3_client:
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            backups = self.list_backups(prefix)
            
            deleted_count = 0
            bucket = self.config['aws']['bucket']
            
            for backup in backups:
                if backup['last_modified'].replace(tzinfo=None) < cutoff_date:
                    self.s3_client.delete_object(Bucket=bucket, Key=backup['key'])
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup['key']}")
            
            return deleted_count
            
        except ClientError as e:
            logger.error(f"Failed to delete old backups: {e}")
            return 0

class DisasterRecoveryManager:
    """Main disaster recovery and backup system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        
        # Initialize managers
        self.db_manager = DatabaseBackupManager(self.config['database']['path'])
        self.file_manager = FileBackupManager()
        self.cloud_manager = CloudBackupManager(self.config.get('cloud', {}))
        
        # Backup jobs and records
        self.backup_jobs = {}
        self.backup_records = []
        
        # Load configuration
        self._load_backup_jobs()
        
        # Start scheduler
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        # Statistics
        self.stats = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'total_backup_size': 0,
            'last_backup_time': None
        }
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            'backup_directory': 'backups',
            'database': {
                'path': 'data/mercedes_obd.db'
            },
            'cloud': {
                'aws': {
                    'enabled': False,
                    'bucket': 'mercedes-obd-backups',
                    'access_key_id': '',
                    'secret_access_key': '',
                    'region': 'us-east-1'
                }
            },
            'default_jobs': [
                {
                    'name': 'Database Backup',
                    'source_paths': ['data/'],
                    'backup_type': 'full',
                    'schedule': '0 2 * * *',  # Daily at 2 AM
                    'retention_days': 30,
                    'compression': True,
                    'encryption': True,
                    'destination': 'local'
                },
                {
                    'name': 'Application Backup',
                    'source_paths': ['mercedes_obd_scanner/', 'web_app/', 'security/'],
                    'backup_type': 'full',
                    'schedule': '0 3 * * 0',  # Weekly on Sunday at 3 AM
                    'retention_days': 90,
                    'compression': True,
                    'encryption': True,
                    'destination': 'local'
                },
                {
                    'name': 'Configuration Backup',
                    'source_paths': ['*.yaml', '*.json', '*.conf'],
                    'backup_type': 'full',
                    'schedule': '0 1 * * *',  # Daily at 1 AM
                    'retention_days': 60,
                    'compression': True,
                    'encryption': False,
                    'destination': 'local'
                }
            ]
        }
    
    def _load_backup_jobs(self):
        """Load backup jobs from configuration"""
        for job_config in self.config.get('default_jobs', []):
            job = BackupJob(
                job_id=str(len(self.backup_jobs) + 1),
                name=job_config['name'],
                source_paths=job_config['source_paths'],
                backup_type=job_config['backup_type'],
                schedule=job_config['schedule'],
                retention_days=job_config['retention_days'],
                compression=job_config['compression'],
                encryption=job_config['encryption'],
                destination=job_config['destination'],
                enabled=True
            )
            self.backup_jobs[job.job_id] = job
    
    def _run_scheduler(self):
        """Run backup scheduler"""
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    def create_backup_job(self, job_config: Dict[str, Any]) -> str:
        """Create new backup job"""
        job_id = str(len(self.backup_jobs) + 1)
        
        job = BackupJob(
            job_id=job_id,
            name=job_config['name'],
            source_paths=job_config['source_paths'],
            backup_type=job_config.get('backup_type', 'full'),
            schedule=job_config.get('schedule', '0 2 * * *'),
            retention_days=job_config.get('retention_days', 30),
            compression=job_config.get('compression', True),
            encryption=job_config.get('encryption', False),
            destination=job_config.get('destination', 'local'),
            enabled=job_config.get('enabled', True)
        )
        
        self.backup_jobs[job_id] = job
        
        # Schedule the job
        if job.enabled:
            self._schedule_job(job)
        
        logger.info(f"Created backup job: {job.name}")
        return job_id
    
    def _schedule_job(self, job: BackupJob):
        """Schedule a backup job"""
        # Parse cron-like schedule (simplified)
        # In production, use proper cron parser like croniter
        if job.schedule == '0 2 * * *':  # Daily at 2 AM
            schedule.every().day.at("02:00").do(self._run_backup_job, job.job_id)
        elif job.schedule == '0 3 * * 0':  # Weekly on Sunday at 3 AM
            schedule.every().sunday.at("03:00").do(self._run_backup_job, job.job_id)
        elif job.schedule == '0 1 * * *':  # Daily at 1 AM
            schedule.every().day.at("01:00").do(self._run_backup_job, job.job_id)
    
    def _run_backup_job(self, job_id: str):
        """Execute backup job"""
        if job_id not in self.backup_jobs:
            logger.error(f"Backup job not found: {job_id}")
            return
        
        job = self.backup_jobs[job_id]
        
        if not job.enabled:
            logger.info(f"Backup job disabled: {job.name}")
            return
        
        logger.info(f"Starting backup job: {job.name}")
        
        try:
            # Execute backup
            backup_record = self._execute_backup(job)
            
            # Update job status
            job.last_run = datetime.now()
            job.last_status = backup_record.status
            
            # Store record
            self.backup_records.append(backup_record)
            
            # Update statistics
            self.stats['total_backups'] += 1
            if backup_record.status == 'success':
                self.stats['successful_backups'] += 1
            else:
                self.stats['failed_backups'] += 1
            
            self.stats['total_backup_size'] += backup_record.file_size
            self.stats['last_backup_time'] = backup_record.timestamp
            
            # Clean up old backups
            self._cleanup_old_backups(job)
            
            logger.info(f"Backup job completed: {job.name} - {backup_record.status}")
            
        except Exception as e:
            logger.error(f"Backup job failed: {job.name} - {e}")
            job.last_status = 'failed'
    
    def _execute_backup(self, job: BackupJob) -> BackupRecord:
        """Execute backup operation"""
        import uuid
        
        backup_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # Generate backup filename
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{job.name.lower().replace(' ', '_')}_{date_str}.tar"
        if job.compression:
            backup_filename += ".gz"
        if job.encryption:
            backup_filename += ".enc"
        
        backup_path = os.path.join(self.config['backup_directory'], backup_filename)
        
        # Create backup
        result = self.file_manager.create_backup_archive(
            job.source_paths,
            backup_path,
            job.compression,
            job.encryption
        )
        
        # Upload to cloud if configured
        if job.destination == 'cloud' and self.cloud_manager.s3_client:
            s3_key = f"backups/{backup_filename}"
            if result['success']:
                cloud_success = self.cloud_manager.upload_backup(backup_path, s3_key)
                if cloud_success:
                    # Remove local file after successful upload
                    os.remove(backup_path)
                    backup_path = f"s3://{self.config['cloud']['aws']['bucket']}/{s3_key}"
        
        # Create backup record
        record = BackupRecord(
            backup_id=backup_id,
            job_id=job.job_id,
            timestamp=timestamp,
            backup_type=job.backup_type,
            file_path=backup_path,
            file_size=result['file_size'],
            checksum=result['checksum'],
            status='success' if result['success'] else 'failed',
            duration_seconds=result['duration_seconds'],
            files_backed_up=result['files_backed_up'],
            errors=result['errors']
        )
        
        return record
    
    def _cleanup_old_backups(self, job: BackupJob):
        """Clean up old backups based on retention policy"""
        cutoff_date = datetime.now() - timedelta(days=job.retention_days)
        
        # Clean up local backups
        backup_dir = self.config['backup_directory']
        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                file_path = os.path.join(backup_dir, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_date and job.name.lower().replace(' ', '_') in filename:
                        os.remove(file_path)
                        logger.info(f"Deleted old backup: {filename}")
        
        # Clean up cloud backups
        if job.destination == 'cloud' and self.cloud_manager.s3_client:
            prefix = f"backups/{job.name.lower().replace(' ', '_')}"
            deleted_count = self.cloud_manager.delete_old_backups(prefix, job.retention_days)
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old cloud backups")
    
    def run_backup_now(self, job_id: str) -> bool:
        """Run backup job immediately"""
        if job_id not in self.backup_jobs:
            logger.error(f"Backup job not found: {job_id}")
            return False
        
        try:
            self._run_backup_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Manual backup failed: {e}")
            return False
    
    def restore_from_backup(self, backup_id: str, restore_path: str) -> bool:
        """Restore from backup"""
        # Find backup record
        backup_record = None
        for record in self.backup_records:
            if record.backup_id == backup_id:
                backup_record = record
                break
        
        if not backup_record:
            logger.error(f"Backup record not found: {backup_id}")
            return False
        
        try:
            backup_path = backup_record.file_path
            
            # Download from cloud if needed
            if backup_path.startswith('s3://'):
                s3_key = backup_path.replace(f"s3://{self.config['cloud']['aws']['bucket']}/", "")
                local_backup_path = os.path.join(self.config['backup_directory'], f"restore_{backup_id}.tar.gz")
                
                if not self.cloud_manager.download_backup(s3_key, local_backup_path):
                    return False
                
                backup_path = local_backup_path
            
            # Get job configuration for encryption info
            job = self.backup_jobs.get(backup_record.job_id)
            encryption = job.encryption if job else False
            
            # Restore files
            success = self.file_manager.restore_from_archive(backup_path, restore_path, encryption)
            
            # Clean up downloaded file
            if backup_record.file_path.startswith('s3://') and os.path.exists(backup_path):
                os.remove(backup_path)
            
            if success:
                logger.info(f"Restore completed: {backup_id} -> {restore_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup system status"""
        return {
            'statistics': self.stats,
            'active_jobs': len([j for j in self.backup_jobs.values() if j.enabled]),
            'total_jobs': len(self.backup_jobs),
            'recent_backups': [r.to_dict() for r in self.backup_records[-10:]],
            'next_scheduled': self._get_next_scheduled_backup()
        }
    
    def _get_next_scheduled_backup(self) -> Optional[str]:
        """Get next scheduled backup time"""
        # In production, calculate from actual schedule
        return "Next backup scheduled for tomorrow at 2:00 AM"
    
    def test_disaster_recovery(self) -> Dict[str, Any]:
        """Test disaster recovery procedures"""
        test_results = {
            'database_backup': False,
            'file_backup': False,
            'cloud_connectivity': False,
            'restore_test': False,
            'overall_status': 'failed'
        }
        
        try:
            # Test database backup
            test_db_backup = os.path.join(self.config['backup_directory'], 'test_db_backup.db')
            test_results['database_backup'] = self.db_manager.backup_database(test_db_backup)
            
            # Test file backup
            test_file_backup = os.path.join(self.config['backup_directory'], 'test_file_backup.tar.gz')
            result = self.file_manager.create_backup_archive(['README.md'], test_file_backup)
            test_results['file_backup'] = result['success']
            
            # Test cloud connectivity
            if self.cloud_manager.s3_client:
                backups = self.cloud_manager.list_backups()
                test_results['cloud_connectivity'] = True
            
            # Test restore
            if test_results['file_backup']:
                test_restore_path = os.path.join(self.config['backup_directory'], 'test_restore')
                test_results['restore_test'] = self.file_manager.restore_from_archive(
                    test_file_backup, test_restore_path
                )
            
            # Overall status
            if all(test_results[key] for key in ['database_backup', 'file_backup']):
                test_results['overall_status'] = 'passed'
            
            # Cleanup test files
            for test_file in [test_db_backup, test_file_backup]:
                if os.path.exists(test_file):
                    os.remove(test_file)
            
            test_restore_path = os.path.join(self.config['backup_directory'], 'test_restore')
            if os.path.exists(test_restore_path):
                shutil.rmtree(test_restore_path)
            
        except Exception as e:
            logger.error(f"Disaster recovery test failed: {e}")
        
        return test_results

if __name__ == "__main__":
    # Demo usage
    print("Mercedes W222 OBD Scanner - Disaster Recovery Demo")
    print("=" * 60)
    
    # Initialize disaster recovery system
    dr_manager = DisasterRecoveryManager()
    
    # Test disaster recovery
    print("1. Testing disaster recovery procedures...")
    test_results = dr_manager.test_disaster_recovery()
    
    print("Test Results:")
    for test, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test}: {status}")
    
    # Get backup status
    print(f"\n2. Backup system status:")
    status = dr_manager.get_backup_status()
    print(f"  Active jobs: {status['active_jobs']}")
    print(f"  Total backups: {status['statistics']['total_backups']}")
    print(f"  Success rate: {status['statistics']['successful_backups']}/{status['statistics']['total_backups']}")
    
    # Create test backup job
    print(f"\n3. Creating test backup job...")
    job_config = {
        'name': 'Test Backup',
        'source_paths': ['README.md'],
        'backup_type': 'full',
        'schedule': '0 * * * *',  # Hourly
        'retention_days': 7,
        'compression': True,
        'encryption': False,
        'destination': 'local',
        'enabled': True
    }
    
    job_id = dr_manager.create_backup_job(job_config)
    print(f"  Created job ID: {job_id}")
    
    # Run backup immediately
    print(f"\n4. Running test backup...")
    success = dr_manager.run_backup_now(job_id)
    print(f"  Backup result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    # Show updated status
    status = dr_manager.get_backup_status()
    if status['recent_backups']:
        latest_backup = status['recent_backups'][-1]
        print(f"  Latest backup: {latest_backup['status']} - {latest_backup['files_backed_up']} files")
    
    print(f"\nDisaster recovery system ready! 🚀")
