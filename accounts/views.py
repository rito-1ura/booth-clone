from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .forms import CustomUserCreationForm
from .models import Creator


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            email = form.cleaned_data.get('email')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(email=email, password=raw_password)
            if user:
                login(request, user)
            messages.success(request, 'アカウントを作成しました！')
            return redirect('shop:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def become_creator_view(request):
    user = request.user
    if hasattr(user, 'creator'):
        messages.info(request, '既にクリエイター登録済みです。')
        return redirect('creators:dashboard')

    if request.method == 'POST':
        pen_name = request.POST.get('pen_name', '').strip()
        if not pen_name:
            messages.error(request, 'ペンネームを入力してください。')
            return render(request, 'accounts/become_creator.html')
        Creator.objects.create(
            user=user,
            pen_name=pen_name,
        )
        user.is_creator = True
        user.save(update_fields=['is_creator'])
        messages.success(request, 'クリエイター登録が完了しました！')
        return redirect('creators:dashboard')
    return render(request, 'accounts/become_creator.html')
