from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404

from .models import Student
from .forms import StudentForm


def staff_required(view_func):
    return user_passes_test(
        lambda user: user.is_staff,
        login_url="login"
    )(view_func)


def login_page(request):
    return render(request, "core/login.html")


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html")


@login_required
@staff_required
def student_list(request):
    students = Student.objects.all()
    return render(request, "core/student_list.html", {"students": students})


@login_required
@staff_required
def student_create(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("student_list")
    else:
        form = StudentForm()

    return render(request, "core/student_form.html", {
        "form": form,
        "title": "Add Student"
    })


@login_required
@staff_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect("student_list")
    else:
        form = StudentForm(instance=student)

    return render(request, "core/student_form.html", {
        "form": form,
        "title": "Update Student"
    })