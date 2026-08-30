import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_external_id(
        self, merchant_id: uuid.UUID, external_customer_id: str
    ) -> Optional[Customer]:
        return (
            self.db.query(Customer)
            .filter(
                Customer.merchant_id == merchant_id,
                Customer.external_customer_id == external_customer_id,
            )
            .one_or_none()
        )

    def get_or_create(
        self, merchant_id: uuid.UUID, external_customer_id: Optional[str]
    ) -> Optional[Customer]:
        if not external_customer_id:
            return None

        existing = self.get_by_external_id(merchant_id, external_customer_id)
        if existing:
            return existing

        customer = Customer(
            merchant_id=merchant_id,
            external_customer_id=external_customer_id,
        )
        self.db.add(customer)
        self.db.flush()
        return customer
