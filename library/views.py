from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from accounts.decorators import teacher_required, student_required
from .models import Resource
from core.models import Subject, Class
from students.models import Student


@teacher_required
def teacher_library(request):
    """Teacher's library — view all resources they uploaded."""
    resources = Resource.objects.filter(uploaded_by=request.user).select_related('subject', 'target_class').order_by('-created_at')

    subjects = Subject.objects.all()
    total = resources.count()

    # Filter
    q = request.GET.get('q', '')
    subject_id = request.GET.get('subject', '')
    rtype = request.GET.get('type', '')

    if q:
        resources = resources.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if subject_id:
        resources = resources.filter(subject_id=subject_id)
    if rtype:
        resources = resources.filter(resource_type=rtype)

    context = {
        'resources': resources,
        'subjects': subjects,
        'resource_types': Resource.RESOURCE_TYPES,
        'total': total,
        'q': q,
        'selected_subject': subject_id,
        'selected_type': rtype,
    }
    return render(request, 'library/teacher_library.html', context)


@teacher_required
def upload_resource(request):
    """Teacher uploads a new resource."""
    subjects = Subject.objects.all()
    classes = Class.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        resource_type = request.POST.get('resource_type', 'document')
        subject_id = request.POST.get('subject_id') or None
        class_id = request.POST.get('class_id') or None
        external_url = request.POST.get('external_url', '').strip()
        uploaded_file = request.FILES.get('file')
        is_published = request.POST.get('is_published') == 'on'

        errors = []
        if not title:
            errors.append('Title is required.')
        if not uploaded_file and not external_url:
            errors.append('Please upload a file OR provide an external URL.')

        if not errors:
            resource = Resource(
                title=title,
                description=description,
                resource_type=resource_type,
                external_url=external_url,
                uploaded_by=request.user,
                is_published=is_published,
            )
            if uploaded_file:
                resource.file = uploaded_file
            if subject_id:
                resource.subject_id = subject_id
            if class_id:
                resource.target_class_id = class_id
            resource.save()
            messages.success(request, f'Resource "{title}" uploaded successfully!')
            return redirect('teacher_library')
        else:
            for err in errors:
                messages.error(request, err)

    context = {
        'subjects': subjects,
        'classes': classes,
        'resource_types': Resource.RESOURCE_TYPES,
    }
    return render(request, 'library/upload_resource.html', context)


@teacher_required
def delete_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        name = resource.title
        resource.delete()
        messages.success(request, f'Resource "{name}" deleted.')
    return redirect('teacher_library')


@teacher_required
def edit_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk, uploaded_by=request.user)
    subjects = Subject.objects.all()
    classes = Class.objects.all()

    if request.method == 'POST':
        resource.title = request.POST.get('title', resource.title).strip()
        resource.description = request.POST.get('description', '').strip()
        resource.resource_type = request.POST.get('resource_type', resource.resource_type)
        resource.external_url = request.POST.get('external_url', '').strip()
        resource.is_published = request.POST.get('is_published') == 'on'
        subject_id = request.POST.get('subject_id') or None
        class_id = request.POST.get('class_id') or None
        resource.subject_id = subject_id
        resource.target_class_id = class_id
        if request.FILES.get('file'):
            resource.file = request.FILES['file']
        resource.save()
        messages.success(request, 'Resource updated successfully!')
        return redirect('teacher_library')

    context = {
        'resource': resource,
        'subjects': subjects,
        'classes': classes,
        'resource_types': Resource.RESOURCE_TYPES,
    }
    return render(request, 'library/edit_resource.html', context)


@student_required
def student_library(request):
    """Student's library — browse published resources available to them."""
    try:
        student = Student.objects.get(user=request.user)
        student_class = student.class_enrolled
    except Student.DoesNotExist:
        student_class = None

    # Show resources for their class OR resources open to everyone (target_class=None)
    resources = Resource.objects.filter(is_published=True).filter(
        Q(target_class__isnull=True) | Q(target_class=student_class)
    ).select_related('subject', 'uploaded_by', 'target_class').order_by('-created_at')

    subjects = Subject.objects.filter(id__in=resources.values_list('subject_id', flat=True).distinct())

    # Filters
    q = request.GET.get('q', '')
    subject_id = request.GET.get('subject', '')
    rtype = request.GET.get('type', '')

    if q:
        resources = resources.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if subject_id:
        resources = resources.filter(subject_id=subject_id)
    if rtype:
        resources = resources.filter(resource_type=rtype)

    context = {
        'resources': resources,
        'subjects': subjects,
        'resource_types': Resource.RESOURCE_TYPES,
        'q': q,
        'selected_subject': subject_id,
        'selected_type': rtype,
        'total': resources.count(),
    }
    return render(request, 'library/student_library.html', context)


@student_required
def view_resource(request, pk):
    """Student views / accesses a resource."""
    try:
        student = Student.objects.get(user=request.user)
        student_class = student.class_enrolled
    except Student.DoesNotExist:
        student_class = None

    resource = get_object_or_404(
        Resource,
        pk=pk,
        is_published=True
    )

    # Check access
    if resource.target_class and resource.target_class != student_class:
        messages.error(request, 'You do not have access to this resource.')
        return redirect('student_library')

    # Increment view count
    Resource.objects.filter(pk=pk).update(view_count=resource.view_count + 1)

    # Prepare embed URL if YouTube
    embed_url = None
    if resource.external_url:
        if 'youtube.com/watch?v=' in resource.external_url:
            embed_url = resource.external_url.replace('watch?v=', 'embed/')
        elif 'youtu.be/' in resource.external_url:
            embed_url = resource.external_url.replace('youtu.be/', 'www.youtube.com/embed/')

    context = {'resource': resource, 'embed_url': embed_url}
    return render(request, 'library/view_resource.html', context)
