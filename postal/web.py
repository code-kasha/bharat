from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render

from postal.importer import ImportFailure, parse_csv, replace_dataset
from postal.models import Dataset
from postal.queries import is_pin, offices_for_pin, search_offices

PAGE_SIZE = 25


def lookup(request):
    """Server-rendered search: one request per page, no scripts or external assets."""
    query = request.GET.get("q", "").strip()
    context = {
        "query": query,
        "dataset": Dataset.objects.filter(pk=1).first(),
        "allow_source_change": settings.ALLOW_SOURCE_CHANGE,
        "updated": request.GET.get("updated") == "1",
    }
    if not query:
        return render(request, "postal/lookup.html", context)
    if query.isdigit():
        if not is_pin(query):
            context["error"] = "A PIN has exactly 6 digits and cannot start with 0."
        else:
            offices = offices_for_pin(query)
    elif not 2 <= len(query) <= 100:
        context["error"] = "Enter a 6-digit PIN, or 2 to 100 characters of a place name."
    else:
        offices = search_offices(query)
    if "error" in context:
        return render(request, "postal/lookup.html", context, status=400)
    context["page"] = Paginator(offices, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "postal/lookup.html", context)


class SourceForm(forms.Form):
    file = forms.FileField(error_messages={"required": "Choose a CSV file to upload."})
    source = forms.CharField(
        max_length=500, error_messages={"required": "Say where the data came from."}
    )
    source_date = forms.DateField(
        required=False, error_messages={"invalid": "Enter a date like 2025-06-30."}
    )
    source_period = forms.CharField(max_length=100, required=False)

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > settings.SOURCE_UPLOAD_MAX_BYTES:
            limit = settings.SOURCE_UPLOAD_MAX_BYTES // (1024 * 1024)
            raise forms.ValidationError(f"The file is larger than {limit} MB.")
        return upload

    def clean(self):
        data = super().clean()
        if data.get("source_date") and data.get("source_period"):
            self.add_error("source_period", "Give an exact date or an approximate one, not both.")
        if self.errors:
            return data
        try:
            self.parsed = parse_csv(data["file"].read())
        except ImportFailure as exc:
            self.add_error("file", str(exc))
            return data
        self.parsed.source_date = data.get("source_date")
        return data


def change_source(request):
    """Local-only: replace the directory from an uploaded CSV, validated before any write."""
    if not settings.ALLOW_SOURCE_CHANGE:
        raise Http404("Changing the source is disabled.")
    form = SourceForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        replace_dataset(
            form.parsed,
            source=form.cleaned_data["source"].strip(),
            source_period=form.cleaned_data["source_period"].strip(),
        )
        return redirect("/?updated=1")
    context = {"form": form, "max_mb": settings.SOURCE_UPLOAD_MAX_BYTES // (1024 * 1024)}
    return render(request, "postal/source.html", context, status=400 if form.errors else 200)


def favicon(request):
    # Some browsers request /favicon.ico regardless of the page's icon; a cached empty
    # response stops a 404 round trip on every page.
    response = HttpResponse(status=204)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
