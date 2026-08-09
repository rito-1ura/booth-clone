// Booth Clone — Main JavaScript
(function () {
    'use strict';

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(function (alert) {
        setTimeout(function () {
            if (alert.parentElement) {
                alert.style.opacity = '0';
                alert.style.transition = 'opacity .3s';
                setTimeout(function () { if (alert.parentElement) alert.remove(); }, 300);
            }
        }, 5000);
    });

    // Payment method selection highlight
    document.querySelectorAll('.payment-option').forEach(function (option) {
        option.addEventListener('click', function () {
            var radio = this.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
            document.querySelectorAll('.payment-option').forEach(function (o) {
                o.classList.remove('selected');
            });
            this.classList.add('selected');
        });
    });

    // Confirm destructive actions
    document.querySelectorAll('[data-confirm]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(this.dataset.confirm || '実行してもよろしいですか？')) {
                e.preventDefault();
            }
        });
    });

    // Image gallery: click thumbnail to change main image
    var thumbnails = document.querySelectorAll('.product-thumbnail');
    var mainImage = document.querySelector('.product-main-image');
    if (thumbnails.length && mainImage) {
        thumbnails.forEach(function (thumb) {
            thumb.addEventListener('click', function () {
                var src = this.src || this.dataset.src;
                if (src) {
                    mainImage.src = src;
                    thumbnails.forEach(function (t) { t.classList.remove('active'); });
                    this.classList.add('active');
                }
            });
        });
    }

})();
