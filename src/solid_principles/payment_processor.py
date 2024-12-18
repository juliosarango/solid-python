from stripe import Charge
import stripe
from stripe.error import StripeError
import os
from pydantic import BaseModel
from typing import Optional, Protocol
from abc import abstractmethod
import uuid

from dotenv import load_dotenv
from dataclasses import dataclass, field

_ = load_dotenv()


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class CustomerData(BaseModel):
    name: str
    contact_info: ContactInfo


class PaymentData(BaseModel):
    amount: int
    source: str


class PaymentResponse(BaseModel):
    status: str
    ammount: int
    transaction_id: Optional[str] = None
    message: Optional[str] = None


@dataclass
class CustomerValidator:
    def validate(self, customer_data: CustomerData):
        if not customer_data.name:
            print("Invalid data: name is required")
            raise ValueError("Invalid data: name is required")

        if not customer_data.contact_info:
            print("Invalid data: contact_info is required")
            raise ValueError("Invalid data: contact_info is required")


@dataclass
class PaymentDataValidator:
    def validate(self, payment_data: PaymentData):
        if not payment_data.source:
            print("Invalid data: source is required")
            raise ValueError("Invalid data: source is required")

        if payment_data.amount <= 0:
            print("Invalid payment data: amount must be positive")
            raise ValueError("Invalid payment data: amount must be positive")


class Notifier(Protocol):
    """
    Protocol for sending notifications.

    This protocol defines the interface for notifiers. Implementations
    should provide a method `send_confirmation` that sends a confirmation
    to the customer.
    """

    @abstractmethod
    def send_confirmation(self, customer_data: CustomerData):
        """Send a confirmation notification to the customer.

        :param customer_data: Data about the customer to notify.
        :type customer_data: CustomerData
        """
        ...


class EmailNotifier(Notifier):
    def send_confirmation(self, customer_data: CustomerData):
        from email.mime.text import MIMEText

        msg = MIMEText("Thank you for your payment.")
        msg["Subject"] = "Payment Confirmation"
        msg["From"] = "no-reply@example.com"
        msg["To"] = customer_data.contact_info.email

        # server = smtplib.SMTP("localhost")
        # server.send_message(msg)
        # server.quit()
        print("Email sent to", customer_data.contact_info.email)


@dataclass
class SMSNotifier(Notifier):
    sms_gateway: str

    def send_confirmation(self, customer_data: CustomerData):
        phone_number = customer_data.contact_info.phone
        print(
            f"send the sms using {self.sms_gateway}: SMS sent to {phone_number}: Thank you for your payment."
        )


@dataclass
class TransactionLogger:
    def log_transaction(
        self,
        customer_data: CustomerData,
        payment_data: PaymentData,
        payment_response: PaymentResponse,
    ):
        with open("transactions.log", "a") as log_file:
            log_file.write(f"{customer_data.name} paid {payment_data.amount}\n")
            log_file.write(f"Payment status: {payment_response.status}\n")
            if payment_response.transaction_id:
                log_file.write(f"Transaction ID: {payment_response.transaction_id}\n")
            log_file.write(f"Message: {payment_response.message}\n")

    def log_refund(self, transaction_id: str, refund_response: PaymentResponse):
        with open("transactions.log", "a") as log_file:
            log_file.write(f"Refund processed for transaction {transaction_id}\n")
            log_file.write(f"Refund status: {refund_response.status}\n")
            log_file.write(f"Message: {refund_response.message}\n")


class PaymentoProcessorProtocol(Protocol):
    """
    Protocol for processing payments.

    This protocol defines the interface for payment processors. Implementations
    should provide a method `process_transaction` that takes customer data and payment data,
    and returns a Stripe Charge object.
    """

    @abstractmethod
    def process_transaction(self, customer_data, payment_data) -> PaymentResponse:
        """Process a payment.

        :param customer_data: Data about the customer making the payment.
        :type customer_data: CustomerData
        :param payment_data: Data about the payment to process.
        :type payment_data: PaymentData
        :return: A Stripe Charge object representing the processed payment.
        :rtype: Charge
        """
        ...


class RefundPaymentProtocol(Protocol):
    @abstractmethod
    def refund_payment(self, transaction_id: str) -> PaymentResponse: ...


class RecurringPaymentProtocol(Protocol):
    @abstractmethod
    def setup_recurring_payment(
        self,
        customer_data: CustomerData,
        payment_data: PaymentData,
    ) -> PaymentResponse: ...


@dataclass
class StripePaymentProcessor(
    PaymentoProcessorProtocol, RefundPaymentProtocol, RecurringPaymentProtocol
):
    def process_transaction(self, customer_data, payment_data) -> PaymentResponse:
        stripe.api_key = os.getenv("STRIPE_API_KEY")

        try:
            charge = stripe.Charge.create(
                amount=payment_data.amount,
                currency="usd",
                source=payment_data.source,
                description="Charge for " + customer_data.name,
            )
            print("Payment successful")
            return PaymentResponse(
                status=charge["status"],
                ammount=charge["amount"],
                transaction_id=charge["id"],
                message="Payment successful",
            )
        except StripeError as e:
            print("Payment failed:", e)
            return PaymentResponse(
                status="failed",
                ammount=payment_data.amount,
                transaction_id=None,
                message=str(e),
            )

    def refund_payment(self, transaction_id: str) -> PaymentResponse:
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        try:
            refund = stripe.Refund.create(charge=transaction_id)
            print("Refund successful")
            return PaymentResponse(
                status=refund["status"],
                amount=refund["amount"],
                transaction_id=refund["id"],
                message="Refund successful",
            )
        except StripeError as e:
            print("Refund failed:", e)
            return PaymentResponse(
                status="failed",
                amount=0,
                transaction_id=None,
                message=str(e),
            )

    def setup_recurring_payment(
        self,
        customer_data: CustomerData,
        payment_data: PaymentData,
    ) -> PaymentResponse:
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        price_id = os.getenv("STRIPE_PRICE_ID", "")
        try:
            customer = self._get_or_create_customer(customer_data)

            payment_method = self._attach_payment_method(
                customer.id, payment_data.source
            )

            self._set_default_payment_method(customer.id, payment_method.id)

            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[
                    {"price": price_id},
                ],
                expand=["latest_invoice.payment_intent"],
            )

            print("Recurring payment setup successful")
            amount = subscription["items"]["data"][0]["price"]["unit_amount"]
            return PaymentResponse(
                status=subscription["status"],
                amount=amount,
                transaction_id=subscription["id"],
                message="Recurring payment setup successful",
            )
        except StripeError as e:
            print("Recurring payment setup failed:", e)
            return PaymentResponse(
                status="failed",
                amount=0,
                transaction_id=None,
                message=str(e),
            )


class OfflinePaymentProcessor(PaymentoProcessorProtocol):
    def process_transaction(self, customer_data, payment_data) -> PaymentResponse:
        return PaymentResponse(
            status="success",
            ammount=payment_data.amount,
            transaction_id=str(uuid.uuid4()),
            message="Offline Payment success",
        )


@dataclass
class PaymentService:
    payment_processor: PaymentoProcessorProtocol
    notifier: Notifier
    customer_validator: CustomerValidator = field(default_factory=CustomerValidator)
    payment_validator: PaymentDataValidator = field(
        default_factory=PaymentDataValidator
    )
    logger = TransactionLogger()

    recurring_processor: Optional[RecurringPaymentProtocol] = None
    refund_processor: Optional[RefundPaymentProtocol] = None

    def process_transaction(self, customer_data, payment_data) -> PaymentResponse:
        self.customer_validator.validate(customer_data)
        self.payment_validator.validate(payment_data)
        payment_response = self.payment_processor.process_transaction(
            customer_data, payment_data
        )
        self.notifier.send_confirmation(customer_data)
        self.logger.log_transaction(customer_data, payment_data, payment_response)
        return payment_response

    def process_refund(self, transaction_id: str) -> PaymentResponse:
        if not self.refund_processor:
            raise Exception("This processor does not support refunds")
        refund_response = self.refund_processor.refund_payment(transaction_id)
        self.logger.log_refund(transaction_id, refund_response)
        return refund_response

    def setup_recurring(self, customer_data, payment_data) -> PaymentResponse:
        if not self.recurring_processor:
            raise Exception("This processor does not support recurring payments")

        recurring_response = self.recurring_processor.setup_recurring_payment(
            customer_data, payment_data
        )
        self.logger.log_transaction(customer_data, payment_data, recurring_response)
        return recurring_response


if __name__ == "__main__":
    stripe_processor = StripePaymentProcessor()
    offline_processor = OfflinePaymentProcessor()

    # customer and payment data
    customer_data_with_email = CustomerData(
        name="John Doe",
        contact_info=ContactInfo(email="e@mail.com"),
    )
    customer_data_with_phone = CustomerData(
        name="Platzi Python",
        contact_info=ContactInfo(phone="1234567890"),
    )
    payment_data = PaymentData(amount=500, source="tok_discover")

    email_notifier = EmailNotifier()
    sms_notifier = SMSNotifier(sms_gateway="This is a mock gateway")

    # # Using Stripe processor with email notifier

    payment_service_email = PaymentService(
        stripe_processor,
        email_notifier,
        refund_processor=stripe_processor,
        recurring_processor=stripe_processor,
    )

    payment_service_email.process_transaction(customer_data_with_email, payment_data)

    # payment processor with sms notifier
    payment_service_sms = PaymentService(stripe_processor, sms_notifier)
    sms_payment_response = payment_service_sms.process_transaction(
        customer_data_with_phone, payment_data
    )

    # Example of processing a refund using Stripe processor

    transacction_id_to_refund = sms_payment_response.transaction_id
    if transacction_id_to_refund:
        payment_service_email.process_refund(transacction_id_to_refund)

    # offline processor with email notifier
    offline_payment_service = PaymentService(offline_processor, email_notifier)
    offline_payment_response = offline_payment_service.process_transaction(
        customer_data_with_email, payment_data
    )

    # Attempt to refund using offline processor (will fail)
    try:
        if offline_payment_response.transaction_id:
            offline_payment_service.process_refund(
                offline_payment_response.transaction_id
            )
    except Exception as e:
        print(e)

    # Attempt to set up recurring payment using offline processor (will fail)
    try:
        offline_payment_service.setup_recurring(customer_data_with_email, payment_data)

    except Exception as e:
        print(
            f"Recurring payment setup failed and PaymentService raised an exception {e}"
        )

    try:
        error_payment_data = PaymentData(amount=700, source="tok_radarBlock")
        payment_service_email.process_transaction(
            customer_data_with_email, error_payment_data
        )
    except Exception as e:
        print(e)

    # Set up recurrence
    recurring_payment_data = PaymentData(amount=100, source="pm_card_visa")
    payment_service_email.setup_recurring(
        customer_data_with_email, recurring_payment_data
    )
