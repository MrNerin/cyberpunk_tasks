// Toggle compact sidebar
function toggleSidebarCompact() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('compact');

    // Save preference to localStorage
    const isCompact = sidebar.classList.contains('compact');
    localStorage.setItem('sidebarCompact', isCompact);
}

// Initialize sidebar state
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const savedState = localStorage.getItem('sidebarCompact');

    // Set initial state (default to compact)
    if (savedState === 'false') {
        sidebar.classList.remove('compact');
    } else {
        sidebar.classList.add('compact');
    }
}

// Update your existing DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initSidebar();

    // Update active link based on current page
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});