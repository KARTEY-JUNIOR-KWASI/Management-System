/**
 * 🎓 EduMS Interactive Onboarding Tour
 * Powered by Driver.js
 */

document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const hasCompletedOnboarding = body.getAttribute('data-onboarding-completed') === 'true';
    const userRole = body.getAttribute('data-user-role');
    const apiEndpoint = "/accounts/api/onboarding/complete/";

    // 🛡️ Auto-start logic: Only start if the flag is false and it's a dashboard page
    const autoStart = !hasCompletedOnboarding && 
                     (window.location.pathname.includes('/dashboard/') || window.location.pathname === '/');

    const driver = window.driver.js.driver;

    const tour = driver({
        showProgress: true,
        allowClose: true,
        steps: getStepsForRole(userRole),
        onDestroyStarted: () => {
            if (!driver.hasNextStep()) {
                console.log("Tour completed naturally.");
                saveOnboardingStatus();
            }
        },
    });

    if (autoStart) {
        // Subtle delay to allow page rendering
        setTimeout(() => {
            tour.drive();
        }, 1000);
    }

    // Manual Restart Button (if it exists)
    const restartBtn = document.getElementById('restart-tour-btn');
    if (restartBtn) {
        restartBtn.addEventListener('click', (e) => {
            e.preventDefault();
            tour.drive();
        });
    }

    /**
     * Define different steps based on user role
     */
    function getStepsForRole(role) {
        const commonSteps = [
            {
                element: '#sidebarToggle',
                popover: {
                    title: 'Navigation Menu',
                    description: 'Toggle this to expand or collapse the sidebar for better focus.',
                    position: 'bottom'
                }
            },
            {
                element: '#topbarUser',
                popover: {
                    title: 'Your Account',
                    description: 'Access your profile and logout options here.',
                    position: 'bottom'
                }
            }
        ];

        let roleSteps = [];
        if (role === 'admin') {
            roleSteps = [
                {
                    element: '#dashboard-header',
                    popover: {
                        title: 'Admin Command Center',
                        description: 'This is where you monitor global school performance and critical alerts.',
                        position: 'bottom'
                    }
                },
                {
                    element: '#stats-cards',
                    popover: {
                        title: 'Real-time Metrics',
                        description: 'View total students, teachers, and system-wide attendance at a glance.',
                        position: 'bottom'
                    }
                },
                {
                    element: '#sidebar-students',
                    popover: {
                        title: 'Student Admissions',
                        description: 'Manage the entire student lifecycle here.',
                        position: 'right'
                    }
                },
                {
                    element: '#sidebar-teachers',
                    popover: {
                        title: 'Faculty Management',
                        description: 'Assign subjects and track teacher performance.',
                        position: 'right'
                    }
                },
                {
                    element: '#performance-chart',
                    popover: {
                        title: 'Academic Analytics',
                        description: 'Visualize the progress of your institution over time.',
                        position: 'top'
                    }
                }
            ];
        } else if (role === 'teacher') {
            roleSteps = [
                {
                    element: '#teacher-stats',
                    popover: {
                        title: 'Your Performance',
                        description: 'Monitor your classes, attendance, and grading status.',
                        position: 'bottom'
                    }
                }
            ];
        }

        return [...roleSteps, ...commonSteps];
    }

    /**
     * Save status to backend using Fetch (AJAX)
     */
    function saveOnboardingStatus() {
        const csrftoken = getCookie('csrftoken');
        
        fetch(apiEndpoint, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: 'completed' })
        })
        .then(response => response.json())
        .then(data => {
            console.log("Onboarding status updated:", data);
            // Optionally set local storage as fallback
            localStorage.setItem('onboarding_completed', 'true');
        })
        .catch(error => console.error('Error updating onboarding status:', error));
    }

    /**
     * Helper to get CSRF token from cookies
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
