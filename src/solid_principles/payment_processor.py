from stripe import Charge
import stripe
from stripe.error import StripeError
import os
from pydantic import BaseModel
from typing import Optional, Protocol
from abc import abstractmethod

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
       def log(self, customer_data, payment_data, charge:Charge):
           if charge:
            with open("transactions.log", "a") as log_file:
                log_file.write(f"{customer_data.name} paid {payment_data.amount}\n")
                log_file.write(f"Payment status: {charge['status']}\n")
           else:
                with open("transactions.log", "a") as log_file:
                    log_file.write(f"{customer_data.name} paid {payment_data.amount}\n")
                    log_file.write(f"Payment status: Failed\n")

class PaymentoProcessor(Protocol):
    """
    Protocol for processing payments.

    This protocol defines the interface for payment processors. Implementations
    should provide a method `process_transaction` that takes customer data and payment data,
    and returns a Stripe Charge object.
    """
    @abstractmethod
    def process_transaction(self, customer_data, payment_data)->Charge:
        """Process a payment.

        :param customer_data: Data about the customer making the payment.
        :type customer_data: CustomerData
        :param payment_data: Data about the payment to process.
        :type payment_data: PaymentData
        :return: A Stripe Charge object representing the processed payment.
        :rtype: Charge
        """
        ...

            
@dataclass
class StripePaymentProcessor(PaymentoProcessor):
    def process_transaction(self, customer_data, payment_data)->Charge:
        stripe.api_key = os.getenv("STRIPE_API_KEY")

        try:
            charge = stripe.Charge.create(
                amount=payment_data.amount,
                currency="usd",
                source=payment_data.source,
                description="Charge for " + customer_data.name,
            )
            print("Payment successful")
            return charge
        except StripeError as e:
            print("Payment failed:", e)
            raise e
        
@dataclass
class PaymentService:
    customer_validator = CustomerValidator()
    payment_validator = PaymentDataValidator()
    payment_processor:PaymentoProcessor = field(default_factory=StripePaymentProcessor)
    notifier:Notifier = field(default_factory=EmailNotifier)
    logger = TransactionLogger()
    
    def process_transaction(self, customer_data, payment_data)->Charge:
        try:
            self.customer_validator.validate(customer_data)
            self.payment_validator.validate(payment_data)            
        except ValueError as e:
            raise e        
        
        try:
            charge = self.payment_processor.process_transaction(customer_data, payment_data)
            self.notifier.send_confirmation(customer_data)
            self.logger.log(customer_data, payment_data, charge)
            return charge
        except StripeError as e:
            raise e
        

if __name__ == "__main__":
    sms_notifier = SMSNotifier(sms_gateway="This is a mock gateway")
    payment_service = PaymentService(notifier=sms_notifier)
    payment_service_sms_notifier = PaymentService(notifier=sms_notifier)

    customer_data_with_email = CustomerData(
        name= "John Doe",
        contact_info= ContactInfo(email= "e@mail.com"),
    )
    customer_data_with_phone = CustomerData(
        name= "Platzi Python",
        contact_info = ContactInfo(phone= "1234567890"),
    )

    payment_data = PaymentData(amount= 500, source= "tok_discover")

    payment_service_sms_notifier.process_transaction(customer_data_with_email, payment_data)
    payment_service.process_transaction(customer_data_with_phone, payment_data) 
    
    try:
        payment_data = PaymentData(amount= 700, source= "tok_radarBlock")
        payment_service.process_transaction(customer_data_with_phone, payment_data)
    except Exception as e:
        print(e)