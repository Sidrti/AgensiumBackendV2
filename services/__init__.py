"""
Services module for Agensium Backend.
Contains external service integrations.
"""

from .s3_service import S3Service, s3_service

__all__ = ['S3Service', 's3_service']
