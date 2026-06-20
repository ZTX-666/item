from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()

class ViolationRecord(Base):
    """Database model for violation records"""
    __tablename__ = 'violations'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    class_name = Column(String(50))
    description = Column(String(200))
    confidence = Column(Float)
    osha_regulation = Column(String(100))
    image_path = Column(String(200))
    pdf_report_path = Column(String(200))
    email_sent = Column(Integer, default=0)  # 0=False, 1=True
    
    def __repr__(self):
        return f"<Violation(id={self.id}, type={self.class_name}, time={self.timestamp})>"

class Database:
    """Database manager for violation logging"""
    
    def __init__(self, db_path=config.DATABASE_PATH):
        """Initialize database connection"""
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        print(f"Database initialized: {db_path}")
    
    def log_violation(self, violation, image_path="", pdf_path="", email_sent=False):
        """
        Log a violation to the database
        
        Args:
            violation: Violation dictionary
            image_path: Path to violation screenshot
            pdf_path: Path to PDF report
            email_sent: Boolean indicating if email was sent
            
        Returns:
            ViolationRecord object
        """
        record = ViolationRecord(
            timestamp=violation['timestamp'],
            class_name=violation['class_name'],
            description=violation['description'],
            confidence=violation['confidence'],
            osha_regulation=violation['osha_regulation'],
            image_path=image_path,
            pdf_report_path=pdf_path,
            email_sent=1 if email_sent else 0
        )
        
        self.session.add(record)
        self.session.commit()
        
        print(f"Violation logged to database: ID {record.id}")
        return record
    
    def get_violations_by_date(self, date):
        """Get all violations for a specific date"""
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        
        return self.session.query(ViolationRecord).filter(
            ViolationRecord.timestamp >= start,
            ViolationRecord.timestamp <= end
        ).all()
    
    def get_violations_by_type(self, class_name):
        """Get all violations of a specific type"""
        return self.session.query(ViolationRecord).filter_by(
            class_name=class_name
        ).all()
    
    def get_total_violations(self):
        """Get total number of violations"""
        return self.session.query(ViolationRecord).count()
    
    def get_recent_violations(self, limit=10):
        """Get most recent violations"""
        return self.session.query(ViolationRecord).order_by(
            ViolationRecord.timestamp.desc()
        ).limit(limit).all()
    
    def get_violation_stats(self):
        """Get statistics about violations"""
        total = self.get_total_violations()
        
        # Count by type
        types = {}
        for record in self.session.query(ViolationRecord).all():
            types[record.class_name] = types.get(record.class_name, 0) + 1
        
        return {
            'total': total,
            'by_type': types
        }
    
    def close(self):
        """Close database session"""
        self.session.close()
