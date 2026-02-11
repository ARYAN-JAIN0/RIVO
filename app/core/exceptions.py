"""Custom exceptions for the RIVO application."""


class RIVOException(Exception):
    """Base exception for RIVO application."""
    
    pass


class ValidationError(RIVOException):
    """Raised when validation fails."""
    
    pass


class NotFoundError(RIVOException):
    """Raised when a resource is not found."""
    
    pass


class DatabaseError(RIVOException):
    """Raised when a database operation fails."""
    
    pass


class ServiceError(RIVOException):
    """Raised when a service operation fails."""
    
    pass


class ConfigurationError(RIVOException):
    """Raised when configuration is invalid."""
    
    pass


class AuthenticationError(RIVOException):
    """Raised when authentication fails."""
    
    pass
