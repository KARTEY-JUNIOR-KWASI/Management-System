from django.core.management.base import BaseCommand
from library.models import Resource
from accounts.models import User
from core.models import Subject

class Command(BaseCommand):
    help = 'Seeds the library with free global classics (Project Gutenberg)'

    def handle(self, *args, **options):
        # Identify custodian user (assumed to be ID 4 based on previous query or any admin)
        custodian = User.objects.filter(role__in=['admin', 'teacher']).first()
        if not custodian:
            self.stdout.write(self.style.ERROR('No admin or teacher user found to assign books.'))
            return

        # Try to find or create a 'Literature' subject
        subject, _ = Subject.objects.get_or_create(name='Global Literature')

        free_books = [
            {
                'title': 'Pride and Prejudice',
                'url': 'https://www.gutenberg.org/ebooks/1342',
                'desc': 'A romantic masterpiece by Jane Austen following Elizabeth Bennet through issues of manners and marriage.'
            },
            {
                'title': 'The Adventures of Sherlock Holmes',
                'url': 'https://www.gutenberg.org/ebooks/1661',
                'desc': 'The definitive collection of mysteries by Sir Arthur Conan Doyle featuring the world\'s greatest detective.'
            },
            {
                'title': 'Alice\'s Adventures in Wonderland',
                'url': 'https://www.gutenberg.org/ebooks/11',
                'desc': 'Lewis Carroll\'s surreal journey through a rabbit hole into a world of pure imagination.'
            },
            {
                'title': 'Moby Dick; or, The Whale',
                'url': 'https://www.gutenberg.org/ebooks/2701',
                'desc': 'Herman Melville\'s epic struggle between Captain Ahab and the white whale.'
            },
            {
                'title': 'Frankenstein; Or, The Modern Prometheus',
                'url': 'https://www.gutenberg.org/ebooks/84',
                'desc': 'Mary Shelley\'s cautionary tale of scientific ambition and the birth of a monster.'
            },
            {
                'title': 'Dracula',
                'url': 'https://www.gutenberg.org/ebooks/345',
                'desc': 'Bram Stoker\'s foundational vampire novel that defined the genre.'
            },
            {
                'title': 'Grimms\' Fairy Tales',
                'url': 'https://www.gutenberg.org/ebooks/2591',
                'desc': 'A collection of classic folktales that have shaped storytelling for centuries.'
            },
            {
                'title': 'The Odyssey',
                'url': 'https://www.gutenberg.org/ebooks/1727',
                'desc': 'Homer\'s epic voyage of Odysseus as he strives to return home to Ithaca.'
            },
            {
                'title': 'Great Expectations',
                'url': 'https://www.gutenberg.org/ebooks/1400',
                'desc': 'Charles Dickens\' exploration of Pip\'s growth and his search for identity and wealth.'
            },
            {
                'title': 'Treasure Island',
                'url': 'https://www.gutenberg.org/ebooks/120',
                'desc': 'Robert Louis Stevenson\'s classic tale of pirates, parrots, and buried gold.'
            }
        ]

        count = 0
        for book in free_books:
            obj, created = Resource.objects.get_or_create(
                title=book['title'],
                external_url=book['url'],
                defaults={
                    'description': book['desc'],
                    'resource_type': 'link',
                    'is_external': True,
                    'source_name': 'Project Gutenberg',
                    'uploaded_by': custodian,
                    'subject': subject,
                    'is_published': True
                }
            )
            if created:
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully synchronized {count} global classics into the Nexus Library.'))
