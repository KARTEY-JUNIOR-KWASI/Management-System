import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_management.settings')
django.setup()

from library.models import Resource
from accounts.models import User

def seed_external_books():
    print("Initializing Library Seeding Protocol...")

    # We need a user to act as the uploader. We will use the first admin or teacher.
    uploader = User.objects.filter(role__in=['admin', 'teacher']).first()
    if not uploader:
        print("ERROR: No admin or teacher found in the database to act as the uploader.")
        return

    # List of classic, free, public domain books (Project Gutenberg / Open Library)
    books = [
        {
            "title": "Frankenstein; Or, The Modern Prometheus",
            "description": "The classic gothic science fiction novel by Mary Shelley.",
            "external_url": "https://www.gutenberg.org/files/84/84-h/84-h.htm",
            "source_name": "Project Gutenberg",
        },
        {
            "title": "Pride and Prejudice",
            "description": "Jane Austen's classic tale of romance and society.",
            "external_url": "https://www.gutenberg.org/files/1342/1342-h/1342-h.htm",
            "source_name": "Project Gutenberg",
        },
        {
            "title": "A Tale of Two Cities",
            "description": "Historical novel by Charles Dickens set in London and Paris before and during the French Revolution.",
            "external_url": "https://www.gutenberg.org/files/98/98-h/98-h.htm",
            "source_name": "Project Gutenberg",
        },
        {
            "title": "The Time Machine",
            "description": "H.G. Wells' famous science fiction novel about time travel.",
            "external_url": "https://www.gutenberg.org/files/35/35-h/35-h.htm",
            "source_name": "Project Gutenberg",
        },
        {
            "title": "Introduction to Algorithms",
            "description": "Open access course material and algorithmic foundations.",
            "external_url": "https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/6-006-introduction-to-algorithms-fall-2011/lecture-videos/",
            "source_name": "MIT OpenCourseWare",
        },
        {
            "title": "Calculus: Volume 1",
            "description": "OpenStax free interactive textbook for Calculus.",
            "external_url": "https://openstax.org/details/books/calculus-volume-1",
            "source_name": "OpenStax",
        },
        {
            "title": "Chemistry: Atoms First",
            "description": "A free chemistry textbook optimized for mobile and desktop.",
            "external_url": "https://openstax.org/details/books/chemistry-atoms-first-2e",
            "source_name": "OpenStax",
        },
        {
            "title": "The Art of War",
            "description": "An ancient Chinese military treatise dating from the Late Spring and Autumn Period.",
            "external_url": "https://openlibrary.org/works/OL10271707W/The_Art_of_War",
            "source_name": "Open Library",
        }
    ]

    count = 0
    for book_data in books:
        # Prevent exact duplicates
        if not Resource.objects.filter(external_url=book_data['external_url']).exists():
            Resource.objects.create(
                title=book_data['title'],
                description=book_data['description'],
                resource_type='link',
                external_url=book_data['external_url'],
                uploaded_by=uploader,
                is_published=True,
                is_external=True,
                source_name=book_data['source_name'],
                target_class=None  # Null means available to everyone globally
            )
            count += 1
            print(f"Added: {book_data['title']}")
        else:
            print(f"Skipped (Already exists): {book_data['title']}")

    print(f"\nSuccessfully seeded {count} external library books!")

if __name__ == '__main__':
    seed_external_books()
