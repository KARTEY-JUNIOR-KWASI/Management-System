from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

class NotificationService:
    @staticmethod
    def send_institutional_email(subject, recipient_list, template_name, context):
        """
        Generic high-performance email dispatcher.
        """
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@edums.edu')

        try:
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Email delivery failure: {str(e)}")
            return False

    @classmethod
    def notify_result_published(cls, result):
        """Automated alert for parents when a new result is posted."""
        student = result.student
        parent_email = getattr(student, 'parent_email', None)
        
        if not parent_email:
            return False

        context = {
            'student_name': student.user.get_full_name(),
            'subject': result.subject.name,
            'exam_type': result.get_exam_type_display(),
            'score': f"{result.score}/{result.max_score}",
            'percentage': f"{(result.score / result.max_score * 100):.1f}%" if result.max_score > 0 else "N/A",
            'school_name': 'Edu Ms Intelligence'
        }
        
        return cls.send_institutional_email(
            subject=f"Academic Alert: New Result for {student.user.get_full_name()}",
            recipient_list=[parent_email],
            template_name='emails/result_published.html',
            context=context
        )
