document.addEventListener('DOMContentLoaded', () => {
    const navbar = document.querySelector('.navbar');

    if (navbar) {
        const handleScroll = () => navbar.classList.toggle('scrolled', window.scrollY > 10);
        handleScroll();
        window.addEventListener('scroll', handleScroll);
    }

    const revealItems = document.querySelectorAll('.reveal');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    revealItems.forEach((item) => observer.observe(item));
});