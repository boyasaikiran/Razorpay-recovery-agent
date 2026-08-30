import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.merchant import Merchant


class MerchantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, merchant_id: uuid.UUID) -> Optional[Merchant]:
        return self.db.query(Merchant).filter(Merchant.id == merchant_id).one_or_none()

    def get_by_razorpay_merchant_id(self, razorpay_merchant_id: str) -> Optional[Merchant]:
        return (
            self.db.query(Merchant)
            .filter(Merchant.razorpay_merchant_id == razorpay_merchant_id)
            .one_or_none()
        )
