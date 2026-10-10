/**
 * DIGITAL LIBRARY & E-BOOK CIRCULATION PORTAL
 * Interactive client-side dynamics, instant ES6+ search, sorting triggers, and fine calculator
 */

document.addEventListener('DOMContentLoaded', () => {
    initInstantSearch();
    initSortChangeAutoSubmit();
    initIssueDateCalculator();
    initReturnFineCalculator();
    initStandaloneCalculator();
    initAutoDismissAlerts();
    initPasswordVisibilityToggles();
    initPasswordStrengthAndValidation();
    initPasswordResetSuccessRedirect();
});

/* -------------------------------------------------------------
 * 1. INSTANT CLIENT-SIDE CATALOG FILTERING (ES6+)
 * ----------------------------------------------------------- */
function initInstantSearch() {
    const searchInput = document.getElementById('catalogSearch');
    const genreFilter = document.getElementById('genreFilter');
    const availFilter = document.getElementById('availFilter');
    const bookCards = document.querySelectorAll('.book-item-col');
    const resultsCountEl = document.getElementById('visibleBooksCount');
    const noResultsEl = document.getElementById('noResultsMsg');

    if (!searchInput && !genreFilter && !availFilter) return;

    function filterCatalog() {
        const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
        const selectedGenre = (genreFilter ? genreFilter.value : '').toLowerCase().trim();
        const selectedAvail = availFilter ? availFilter.value : 'all';

        let visibleCount = 0;

        bookCards.forEach(card => {
            const title = (card.dataset.title || '').toLowerCase();
            const author = (card.dataset.author || '').toLowerCase();
            const isbn = (card.dataset.isbn || '').toLowerCase();
            const genre = (card.dataset.genre || '').toLowerCase();
            const availableCopies = parseInt(card.dataset.availableCopies || '0', 10);

            // Match text
            const matchesQuery = !query || 
                title.includes(query) || 
                author.includes(query) || 
                isbn.includes(query) || 
                genre.includes(query);

            // Match genre
            const matchesGenre = !selectedGenre || genre === selectedGenre;

            // Match availability
            let matchesAvail = true;
            if (selectedAvail === 'available') {
                matchesAvail = availableCopies > 0;
            } else if (selectedAvail === 'unavailable') {
                matchesAvail = availableCopies === 0;
            }

            if (matchesQuery && matchesGenre && matchesAvail) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        if (resultsCountEl) {
            resultsCountEl.textContent = visibleCount;
        }

        if (noResultsEl) {
            noResultsEl.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }

    if (searchInput) searchInput.addEventListener('input', filterCatalog);
    if (genreFilter) genreFilter.addEventListener('change', filterCatalog);
    if (availFilter) availFilter.addEventListener('change', filterCatalog);
}

/* -------------------------------------------------------------
 * 2. SORT CHANGE AUTO-SUBMIT (FOR PAGINATED DATABASE ORDERING)
 * ----------------------------------------------------------- */
function initSortChangeAutoSubmit() {
    const sortFilter = document.getElementById('sortFilter');
    const searchForm = document.getElementById('searchForm');
    if (sortFilter && searchForm) {
        sortFilter.addEventListener('change', () => {
            searchForm.submit();
        });
    }
}

/* -------------------------------------------------------------
 * 3. BOOK ISSUE WORKFLOW: AUTO DUE DATE (+14 DAYS)
 * ----------------------------------------------------------- */
function initIssueDateCalculator() {
    const issueDateInput = document.getElementById('id_issue_date');
    const dueDateInput = document.getElementById('id_due_date');
    const duePreviewText = document.getElementById('duePreviewText');

    if (!issueDateInput || !dueDateInput) return;

    function updateDueDate() {
        if (!issueDateInput.value) return;
        const issueDate = new Date(issueDateInput.value + 'T00:00:00');
        if (isNaN(issueDate.getTime())) return;

        // Default: 14 days loan period
        const dueDate = new Date(issueDate);
        dueDate.setDate(dueDate.getDate() + 14);

        const yyyy = dueDate.getFullYear();
        const mm = String(dueDate.getMonth() + 1).padStart(2, '0');
        const dd = String(dueDate.getDate()).padStart(2, '0');
        const formattedDate = `${yyyy}-${mm}-${dd}`;

        dueDateInput.value = formattedDate;

        if (duePreviewText) {
            const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
            duePreviewText.textContent = `Standard Due Date (14 days): ${dueDate.toLocaleDateString(undefined, options)}`;
        }
    }

    issueDateInput.addEventListener('change', updateDueDate);
}

/* -------------------------------------------------------------
 * 4. BOOK RETURN WORKFLOW: LIVE OVERDUE & FINE CALCULATION (₹5/day)
 * ----------------------------------------------------------- */
function initReturnFineCalculator() {
    const recordSelect = document.getElementById('id_circulation_record');
    const returnDateInput = document.getElementById('id_return_date');
    const fineRateEl = document.getElementById('fineRateValue');
    const summaryCard = document.getElementById('returnSummaryCard');
    const daysOverdueEl = document.getElementById('calcDaysOverdue');
    const fineAmountEl = document.getElementById('calcFineAmount');
    const statusBadgeEl = document.getElementById('calcStatusBadge');

    if (!recordSelect || !returnDateInput) return;

    const fineRate = fineRateEl ? parseFloat(fineRateEl.dataset.rate || '5.00') : 5.00;

    function calculateReturnFine() {
        const selectedOption = recordSelect.options[recordSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value || !returnDateInput.value) {
            if (summaryCard) summaryCard.style.display = 'none';
            return;
        }

        const dueDateStr = selectedOption.dataset.dueDate;
        if (!dueDateStr) {
            if (summaryCard) summaryCard.style.display = 'none';
            return;
        }

        const dueDate = new Date(dueDateStr + 'T00:00:00');
        const returnDate = new Date(returnDateInput.value + 'T00:00:00');

        if (isNaN(dueDate.getTime()) || isNaN(returnDate.getTime())) return;

        const diffTime = returnDate.getTime() - dueDate.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        const overdueDays = Math.max(0, diffDays);
        const fine = (overdueDays * fineRate).toFixed(2);

        if (summaryCard) summaryCard.style.display = 'block';
        if (daysOverdueEl) daysOverdueEl.textContent = overdueDays;
        if (fineAmountEl) fineAmountEl.textContent = `₹${fine}`;

        if (statusBadgeEl) {
            if (overdueDays > 0) {
                statusBadgeEl.className = 'badge bg-danger p-2 fs-6';
                statusBadgeEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> OVERDUE BY ${overdueDays} DAYS`;
            } else {
                statusBadgeEl.className = 'badge bg-success p-2 fs-6';
                statusBadgeEl.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> RETURNED ON TIME`;
            }
        }
    }

    recordSelect.addEventListener('change', calculateReturnFine);
    returnDateInput.addEventListener('change', calculateReturnFine);

    // Run on initial load if record is preselected
    if (recordSelect.value) {
        calculateReturnFine();
    }
}

/* -------------------------------------------------------------
 * 5. STANDALONE INTERACTIVE DUE DATE & FINE CALCULATOR (₹5/day)
 * ----------------------------------------------------------- */
function initStandaloneCalculator() {
    const calcIssueDate = document.getElementById('calc_issue_date');
    const calcLoanPeriod = document.getElementById('calc_loan_period');
    const calcReturnDate = document.getElementById('calc_return_date');
    const calcDailyRate = document.getElementById('calc_daily_rate');

    const resultDueDate = document.getElementById('result_due_date');
    const resultOverdueDays = document.getElementById('result_overdue_days');
    const resultFineAmount = document.getElementById('result_fine_amount');
    const resultStatusCard = document.getElementById('result_status_card');
    const resultStatusTitle = document.getElementById('result_status_title');
    const resultStatusSub = document.getElementById('result_status_sub');

    if (!calcIssueDate || !calcReturnDate) return;

    function compute() {
        const issueDate = new Date(calcIssueDate.value + 'T00:00:00');
        const periodDays = parseInt(calcLoanPeriod.value || '14', 10);
        const returnDate = new Date(calcReturnDate.value + 'T00:00:00');
        const rate = parseFloat(calcDailyRate.value || '5.00');

        if (isNaN(issueDate.getTime()) || isNaN(returnDate.getTime())) return;

        // Computed Due Date
        const dueDate = new Date(issueDate);
        dueDate.setDate(dueDate.getDate() + periodDays);

        const yyyy = dueDate.getFullYear();
        const mm = String(dueDate.getMonth() + 1).padStart(2, '0');
        const dd = String(dueDate.getDate()).padStart(2, '0');
        const formattedDueDate = `${yyyy}-${mm}-${dd}`;

        const diffTime = returnDate.getTime() - dueDate.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        const overdueDays = Math.max(0, diffDays);
        const totalFine = (overdueDays * rate).toFixed(2);

        if (resultDueDate) resultDueDate.textContent = formattedDueDate;
        if (resultOverdueDays) resultOverdueDays.textContent = `${overdueDays} days`;
        if (resultFineAmount) resultFineAmount.textContent = `₹${totalFine}`;

        if (resultStatusCard && resultStatusTitle && resultStatusSub) {
            if (overdueDays > 0) {
                resultStatusCard.className = 'calc-display-box overdue';
                resultStatusTitle.textContent = `OVERDUE: ₹${totalFine} FINE`;
                resultStatusSub.textContent = `Book is overdue by ${overdueDays} day(s) past the ${periodDays}-day loan period.`;
            } else {
                resultStatusCard.className = 'calc-display-box';
                resultStatusTitle.textContent = 'NO OVERDUE FINE (₹0.00)';
                resultStatusSub.textContent = 'Book returned on or before the due date.';
            }
        }
    }

    [calcIssueDate, calcLoanPeriod, calcReturnDate, calcDailyRate].forEach(input => {
        if (input) {
            input.addEventListener('input', compute);
            input.addEventListener('change', compute);
        }
    });

    compute();
}

/* -------------------------------------------------------------
 * 6. AUTO-DISMISS ALERT NOTIFICATIONS
 * ----------------------------------------------------------- */
function initAutoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (window.bootstrap && bootstrap.Alert) {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                if (bsAlert) bsAlert.close();
            }
        }, 6000);
    });
}

/* -------------------------------------------------------------
 * 7. SHOW / HIDE PASSWORD CONTROLS (INDEPENDENT)
 * ----------------------------------------------------------- */
function initPasswordVisibilityToggles() {
    const toggleButtons = document.querySelectorAll('.toggle-password-btn');
    toggleButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const targetId = button.dataset.target;
            const input = document.getElementById(targetId);
            if (!input) return;

            const icon = button.querySelector('i');
            const isPassword = input.type === 'password';

            if (isPassword) {
                input.type = 'text';
                button.setAttribute('aria-label', 'Hide password');
                button.setAttribute('title', 'Hide password');
                if (icon) {
                    icon.className = 'bi bi-eye-slash';
                }
            } else {
                input.type = 'password';
                button.setAttribute('aria-label', 'Show password');
                button.setAttribute('title', 'Show password');
                if (icon) {
                    icon.className = 'bi bi-eye';
                }
            }
        });
    });
}

/* -------------------------------------------------------------
 * 8. PASSWORD STRENGTH METER & REAL-TIME CONFIRMATION
 * ----------------------------------------------------------- */
function initPasswordStrengthAndValidation() {
    const form = document.getElementById('passwordResetConfirmForm');
    const pwdInput = document.getElementById('id_new_password1');
    const confirmInput = document.getElementById('id_new_password2');
    const strengthBar = document.getElementById('strengthBar');
    const strengthBadge = document.getElementById('strengthBadge');
    const strengthTip = document.getElementById('strengthTip');
    const matchFeedback = document.getElementById('passwordMatchFeedback');
    const submitBtn = document.getElementById('submitResetBtn');

    const reqLength = document.getElementById('reqLength');
    const reqCase = document.getElementById('reqCase');
    const reqNumber = document.getElementById('reqNumber');
    const reqSpecial = document.getElementById('reqSpecial');

    if (!form || !pwdInput) return;

    function updateChecklistItem(el, isValid) {
        if (!el) return;
        const icon = el.querySelector('i');
        if (isValid) {
            el.classList.add('valid');
            if (icon) icon.className = 'bi bi-check-circle-fill text-success me-1';
        } else {
            el.classList.remove('valid');
            if (icon) icon.className = 'bi bi-circle me-1';
        }
    }

    function evaluateStrength(pwd) {
        if (!pwd || pwd.length === 0) {
            return {
                level: 'none',
                percent: 0,
                label: 'Enter password',
                tip: 'Use at least 8 characters with letters, numbers, and symbols.',
                reqs: { length: false, caseReq: false, number: false, special: false }
            };
        }

        const hasMinLen = pwd.length >= 8;
        const hasUpper = /[A-Z]/.test(pwd);
        const hasLower = /[a-z]/.test(pwd);
        const hasCase = hasUpper && hasLower;
        const hasNum = /[0-9]/.test(pwd);
        const hasSpec = /[^A-Za-z0-9]/.test(pwd);

        const reqs = {
            length: hasMinLen,
            caseReq: hasCase,
            number: hasNum,
            special: hasSpec
        };

        // Strict: If length < 8, always Weak regardless of characters
        if (!hasMinLen) {
            const needed = 8 - pwd.length;
            return {
                level: 'weak',
                percent: 25,
                label: 'Weak',
                tip: `Password is too short (needs at least ${needed} more character${needed > 1 ? 's' : ''}).`,
                reqs
            };
        }

        let score = 0;
        if (hasMinLen) score += 2;
        if (pwd.length >= 12) score += 2;
        if (pwd.length >= 16) score += 1;
        if (hasLower) score += 1;
        if (hasUpper) score += 1;
        if (hasNum) score += 1;
        if (hasSpec) score += 1;

        const varietyCount = (hasLower ? 1 : 0) + (hasUpper ? 1 : 0) + (hasNum ? 1 : 0) + (hasSpec ? 1 : 0);

        if (score < 5 || varietyCount < 2) {
            return {
                level: 'weak',
                percent: 33,
                label: 'Weak',
                tip: 'Weak password. Add uppercase letters, numbers, and symbols.',
                reqs
            };
        } else if (score < 8 || varietyCount < 3) {
            return {
                level: 'fair',
                percent: 66,
                label: 'Fair',
                tip: 'Good password. Add special symbols and make it longer for strong security.',
                reqs
            };
        } else {
            return {
                level: 'strong',
                percent: 100,
                label: 'Strong',
                tip: 'Excellent! Strong password meets all security criteria.',
                reqs
            };
        }
    }

    function checkMatch() {
        if (!confirmInput || !matchFeedback) return true;
        const pwd = pwdInput.value;
        const confirm = confirmInput.value;

        if (confirm.length === 0) {
            matchFeedback.style.display = 'none';
            matchFeedback.innerHTML = '';
            confirmInput.classList.remove('is-valid', 'is-invalid');
            return false;
        }

        if (pwd !== confirm) {
            matchFeedback.style.display = 'flex';
            matchFeedback.className = 'match-feedback invalid mt-2';
            matchFeedback.innerHTML = '<i class="bi bi-x-circle-fill text-danger"></i> <span class="text-danger">Passwords do not match.</span>';
            confirmInput.classList.add('is-invalid');
            confirmInput.classList.remove('is-valid');
            return false;
        } else {
            matchFeedback.style.display = 'flex';
            matchFeedback.className = 'match-feedback valid mt-2';
            matchFeedback.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i> <span class="text-success">Passwords match perfectly.</span>';
            confirmInput.classList.add('is-valid');
            confirmInput.classList.remove('is-invalid');
            return true;
        }
    }

    function onPasswordChange() {
        const pwd = pwdInput.value;
        const result = evaluateStrength(pwd);

        if (strengthBar) {
            strengthBar.style.width = result.percent + '%';
            strengthBar.className = 'progress-bar strength-bar ' + (result.level !== 'none' ? result.level : '');
            strengthBar.setAttribute('aria-valuenow', result.percent);
        }

        if (strengthBadge) {
            strengthBadge.textContent = result.label;
            strengthBadge.className = 'badge strength-badge ' + (result.level !== 'none' ? result.level : '');
        }

        if (strengthTip) {
            strengthTip.textContent = result.tip;
        }

        updateChecklistItem(reqLength, result.reqs.length);
        updateChecklistItem(reqCase, result.reqs.caseReq);
        updateChecklistItem(reqNumber, result.reqs.number);
        updateChecklistItem(reqSpecial, result.reqs.special);

        if (confirmInput && confirmInput.value.length > 0) {
            checkMatch();
        }
    }

    pwdInput.addEventListener('input', onPasswordChange);
    pwdInput.addEventListener('keyup', onPasswordChange);

    if (confirmInput) {
        confirmInput.addEventListener('input', checkMatch);
        confirmInput.addEventListener('keyup', checkMatch);
    }

    // Client-side submission check
    form.addEventListener('submit', (e) => {
        const pwd = pwdInput.value;
        const confirm = confirmInput ? confirmInput.value : '';

        if (!pwd || pwd.length === 0) {
            e.preventDefault();
            pwdInput.focus();
            pwdInput.classList.add('is-invalid');
            return false;
        }

        if (pwd.length < 8) {
            e.preventDefault();
            pwdInput.focus();
            pwdInput.classList.add('is-invalid');
            return false;
        }

        if (confirmInput && pwd !== confirm) {
            e.preventDefault();
            confirmInput.focus();
            checkMatch();
            return false;
        }

        // Trigger loading state on button
        if (submitBtn) {
            submitBtn.disabled = true;
            const spinner = submitBtn.querySelector('.btn-spinner');
            const icon = submitBtn.querySelector('.btn-icon');
            const text = submitBtn.querySelector('.btn-text');
            if (spinner) spinner.classList.remove('d-none');
            if (icon) icon.classList.add('d-none');
            if (text) text.textContent = 'Resetting Password...';
        }
    });

    // Run once on load in case browser prefilled
    if (pwdInput.value) {
        onPasswordChange();
    }
}

/* -------------------------------------------------------------
 * 9. SUCCESS PAGE AUTO-REDIRECT COUNTDOWN WITH PAUSE/RESUME
 * ----------------------------------------------------------- */
function initPasswordResetSuccessRedirect() {
    const successPage = document.getElementById('passwordResetSuccessPage');
    if (!successPage) return;

    const countdownEl = document.getElementById('countdownSeconds');
    const progressBar = document.getElementById('countdownProgressBar');
    const toggleBtn = document.getElementById('toggleCountdownBtn');
    const toggleIcon = document.getElementById('toggleCountdownIcon');
    const toggleText = document.getElementById('toggleCountdownText');
    const continueBtn = document.getElementById('continueLoginBtn');
    const spinner = document.getElementById('redirectSpinner');

    const totalSeconds = 5;
    let remaining = totalSeconds;
    let isPaused = false;
    let timerId = null;

    const loginUrl = continueBtn ? continueBtn.getAttribute('href') : '/login/';

    // Respect user's reduced-motion preference
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
        isPaused = true;
        if (toggleIcon) toggleIcon.className = 'bi bi-play-circle me-1';
        if (toggleText) toggleText.textContent = 'Auto-redirect paused (reduced motion)';
        if (spinner) spinner.classList.add('d-none');
        if (progressBar) progressBar.style.width = '100%';
        return;
    }

    timerId = setInterval(() => {
        if (isPaused) return;

        remaining -= 1;
        if (countdownEl) countdownEl.textContent = Math.max(0, remaining);

        if (progressBar) {
            const percent = Math.max(0, (remaining / totalSeconds) * 100);
            progressBar.style.width = percent + '%';
        }

        if (remaining <= 0) {
            clearInterval(timerId);
            window.location.href = loginUrl;
        }
    }, 1000);

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            isPaused = !isPaused;
            if (isPaused) {
                if (toggleIcon) toggleIcon.className = 'bi bi-play-circle me-1';
                if (toggleText) toggleText.textContent = 'Resume auto-redirect';
                if (spinner) spinner.classList.add('d-none');
            } else {
                if (toggleIcon) toggleIcon.className = 'bi bi-pause-circle me-1';
                if (toggleText) toggleText.textContent = 'Pause auto-redirect';
                if (spinner) spinner.classList.remove('d-none');
            }
        });
    }
}

