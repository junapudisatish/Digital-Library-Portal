/**
 * DIGITAL LIBRARY & E-BOOK CIRCULATION PORTAL
 * Interactive client-side dynamics, instant search, and fine calculator
 */

document.addEventListener('DOMContentLoaded', () => {
    initInstantSearch();
    initIssueDateCalculator();
    initReturnFineCalculator();
    initStandaloneCalculator();
    initAutoDismissAlerts();
});

/* -------------------------------------------------------------
 * 1. INSTANT CLIENT-SIDE CATALOG FILTERING
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

    // Initial run
    filterCatalog();
}

/* -------------------------------------------------------------
 * 2. BOOK ISSUE WORKFLOW: AUTO DUE DATE (+14 DAYS)
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
            duePreviewText.textContent = `Default Due Date (14 days): ${dueDate.toLocaleDateString(undefined, options)}`;
        }
    }

    issueDateInput.addEventListener('change', updateDueDate);
}

/* -------------------------------------------------------------
 * 3. BOOK RETURN WORKFLOW: LIVE OVERDUE & FINE CALCULATION
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

    const fineRate = fineRateEl ? parseFloat(fineRateEl.dataset.rate || '1.00') : 1.00;

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
        if (fineAmountEl) fineAmountEl.textContent = `$${fine}`;

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
 * 4. STANDALONE INTERACTIVE DUE DATE & FINE CALCULATOR
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
        const rate = parseFloat(calcDailyRate.value || '1.00');

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
        if (resultFineAmount) resultFineAmount.textContent = `$${totalFine}`;

        if (resultStatusCard && resultStatusTitle && resultStatusSub) {
            if (overdueDays > 0) {
                resultStatusCard.className = 'calc-display-box overdue';
                resultStatusTitle.textContent = `OVERDUE: $${totalFine} FINE`;
                resultStatusSub.textContent = `Book is overdue by ${overdueDays} day(s) past the due date.`;
            } else {
                resultStatusCard.className = 'calc-display-box';
                resultStatusTitle.textContent = 'NO OVERDUE FINE ($0.00)';
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
 * 5. AUTO-DISMISS ALERT MESSAGES
 * ----------------------------------------------------------- */
function initAutoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 6000);
    });
}
