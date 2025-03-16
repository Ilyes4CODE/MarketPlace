from django.db import models
from Auth.models import MarketUser
# Create your models here.
class PredefinedMessage(models.Model):
    """Predefined messages that users can choose from."""
    text = models.TextField()

    def __str__(self):
        return self.text[:50]


class Ticket(models.Model):
    """Support ticket opened by a user."""
    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    user = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.id} - {self.subject}"


class Message(models.Model):
    """Messages exchanged in a ticket."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(MarketUser, on_delete=models.CASCADE)
    content = models.TextField()
    image = models.ImageField(upload_to="messages/", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message by {self.sender} on Ticket {self.ticket.id}"


class Attachment(models.Model):
    """Attachments (images) sent in messages."""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    image = models.ImageField(upload_to="ticket_attachments/")

    def __str__(self):
        return f"Attachment for Message {self.message.id}"