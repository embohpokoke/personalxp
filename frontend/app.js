const { createApp, nextTick } = Vue;

const todayIso = () => new Date().toISOString().slice(0, 10);

createApp({
  data() {
    return {
      booting: true,
      authenticated: false,
      loginPin: "",
      loginActor: "primary",
      loginError: "",
      view: "dashboard",
      loading: false,
      error: "",
      user: null,
      categories: [],
      transactions: [],
      transactionTotal: 0,
      budgets: [],
      monthlySummary: null,
      weeklySummary: null,
      form: this.blankTransaction(),
      budgetForm: {
        category_id: "",
        limit_amount: "",
        period: "monthly",
        start_date: todayIso(),
        end_date: "",
        alert_telegram: true
      },
      filters: {
        q: "",
        source_agent: "",
        category_id: ""
      },
      receiptFile: null,
      receiptName: "",
      dashboardChart: null,
      reportChart: null,
      tabs: [
        { id: "dashboard", label: "Dashboard", icon: "dashboard" },
        { id: "transactions", label: "Transactions", icon: "receipt_long" },
        { id: "add", label: "Add", icon: "add" },
        { id: "budgets", label: "Budgets", icon: "savings" },
        { id: "reports", label: "Reports", icon: "bar_chart" }
      ]
    };
  },
  computed: {
    expenseCategories() {
      return this.categories.filter((category) => category.type === "expense");
    },
    topCategories() {
      const totals = this.monthlySummary?.category_totals || [];
      return totals.filter((item) => item.type === "expense").slice(0, 5);
    },
    recentTransactions() {
      return this.transactions.slice(0, 8);
    },
    totalExpense() {
      return Number(this.monthlySummary?.expense_idr || 0);
    },
    totalIncome() {
      return Number(this.monthlySummary?.income_idr || 0);
    },
    safeToSpend() {
      const activeBudgetTotal = this.budgets.reduce((sum, budget) => {
        if (budget.period === "monthly") return sum + Number(budget.limit_amount || 0);
        return sum;
      }, 0);
      if (!activeBudgetTotal) return Math.max(0, this.totalIncome - this.totalExpense);
      return Math.max(0, activeBudgetTotal - this.totalExpense);
    },
    budgetPercent() {
      const activeBudgetTotal = this.budgets.reduce((sum, budget) => {
        if (budget.period === "monthly") return sum + Number(budget.limit_amount || 0);
        return sum;
      }, 0);
      if (!activeBudgetTotal) return this.totalExpense ? 100 : 0;
      return Math.min(100, Math.round((this.totalExpense / activeBudgetTotal) * 100));
    },
    activeTitle() {
      return this.tabs.find((tab) => tab.id === this.view)?.label || "Dashboard";
    }
  },
  watch: {
    view() {
      nextTick(() => this.renderCharts());
    },
    monthlySummary: {
      deep: true,
      handler() {
        nextTick(() => this.renderCharts());
      }
    }
  },
  async mounted() {
    await this.checkSession();
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  },
  methods: {
    blankTransaction() {
      return {
        amount: "",
        type: "expense",
        category: "",
        merchant: "",
        description: "",
        txn_date: todayIso(),
        currency: "IDR",
        exchange_rate: "1",
        entered_by: "primary"
      };
    },
    async api(path, options = {}) {
      const response = await fetch(path, {
        credentials: "include",
        ...options,
        headers: {
          ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
          ...(options.headers || {})
        }
      });
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const payload = await response.json();
          detail = payload.detail || payload.error || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      if (response.status === 204) return null;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) return response.json();
      return response;
    },
    async checkSession() {
      this.booting = true;
      try {
        const me = await this.api("/api/v1/auth/me");
        this.user = me.user;
        this.authenticated = true;
        await this.loadAll();
      } catch (_) {
        this.authenticated = false;
      } finally {
        this.booting = false;
      }
    },
    async login() {
      this.loginError = "";
      try {
        const payload = await this.api("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ pin: this.loginPin, entered_by: this.loginActor })
        });
        this.user = payload.user;
        this.authenticated = true;
        this.loginPin = "";
        await this.loadAll();
      } catch (error) {
        this.loginError = error.message;
      }
    },
    async logout() {
      await this.api("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
      this.authenticated = false;
      this.view = "dashboard";
      this.user = null;
    },
    async loadAll() {
      this.loading = true;
      this.error = "";
      try {
        await Promise.all([
          this.loadCategories(),
          this.loadTransactions(),
          this.loadBudgets(),
          this.loadSummaries()
        ]);
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    async loadCategories() {
      this.categories = await this.api("/api/v1/categories");
    },
    async loadTransactions() {
      const params = new URLSearchParams({ limit: "50" });
      if (this.filters.q) params.set("q", this.filters.q);
      if (this.filters.source_agent) params.set("source_agent", this.filters.source_agent);
      if (this.filters.category_id) params.set("category_id", this.filters.category_id);
      const payload = await this.api(`/api/v1/transactions?${params.toString()}`);
      this.transactions = payload.items;
      this.transactionTotal = payload.total;
    },
    async loadBudgets() {
      this.budgets = await this.api("/api/v1/budgets");
    },
    async loadSummaries() {
      const [monthly, weekly] = await Promise.all([
        this.api("/api/v1/reports/summary?period=monthly"),
        this.api("/api/v1/reports/summary?period=weekly")
      ]);
      this.monthlySummary = monthly;
      this.weeklySummary = weekly;
    },
    async submitTransaction() {
      this.error = "";
      const data = new FormData();
      Object.entries(this.form).forEach(([key, value]) => {
        if (value !== "" && value !== null && value !== undefined) data.append(key, value);
      });
      if (this.receiptFile) data.append("receipt", this.receiptFile);
      try {
        await this.api("/api/v1/transactions", { method: "POST", body: data });
        this.form = this.blankTransaction();
        this.receiptFile = null;
        this.receiptName = "";
        this.$refs.receiptInput && (this.$refs.receiptInput.value = "");
        await this.loadAll();
        this.view = "transactions";
      } catch (error) {
        this.error = error.message;
      }
    },
    async deleteTransaction(transaction) {
      if (!confirm(`Delete ${transaction.merchant || transaction.category || "transaction"}?`)) return;
      await this.api(`/api/v1/transactions/${transaction.id}`, { method: "DELETE" });
      await this.loadAll();
    },
    async submitBudget() {
      this.error = "";
      try {
        await this.api("/api/v1/budgets", {
          method: "POST",
          body: JSON.stringify({
            category_id: Number(this.budgetForm.category_id),
            limit_amount: this.budgetForm.limit_amount,
            period: this.budgetForm.period,
            start_date: this.budgetForm.start_date,
            end_date: this.budgetForm.end_date || null,
            alert_telegram: this.budgetForm.alert_telegram
          })
        });
        this.budgetForm.limit_amount = "";
        this.budgetForm.category_id = "";
        await this.loadAll();
      } catch (error) {
        this.error = error.message;
      }
    },
    onReceiptChange(event) {
      this.receiptFile = event.target.files?.[0] || null;
      this.receiptName = this.receiptFile ? this.receiptFile.name : "";
    },
    async downloadPdf() {
      const now = new Date();
      window.location.href = `/api/v1/reports/monthly.pdf?year=${now.getFullYear()}&month=${now.getMonth() + 1}`;
    },
    setView(view) {
      this.view = view;
      if (view === "transactions") this.loadTransactions();
    },
    renderCharts() {
      if (!this.authenticated || !window.Chart) return;
      const labels = this.topCategories.map((item) => item.category);
      const values = this.topCategories.map((item) => Number(item.total_idr));
      const colors = ["#00c292", "#fe7d5e", "#db8cfa", "#41dfac", "#a53b22"];

      if (this.$refs.dashboardChart) {
        this.dashboardChart?.destroy();
        this.dashboardChart = new Chart(this.$refs.dashboardChart, {
          type: "doughnut",
          data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            cutout: "72%"
          }
        });
      }

      if (this.$refs.reportChart) {
        this.reportChart?.destroy();
        this.reportChart = new Chart(this.$refs.reportChart, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "Expenses",
              data: values,
              backgroundColor: colors,
              borderRadius: 12
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { grid: { display: false } },
              y: { ticks: { callback: (value) => this.compactMoney(value) } }
            }
          }
        });
      }
    },
    formatMoney(value) {
      return new Intl.NumberFormat("id-ID", {
        style: "currency",
        currency: "IDR",
        maximumFractionDigits: 0
      }).format(Number(value || 0));
    },
    compactMoney(value) {
      const number = Number(value || 0);
      if (number >= 1000000) return `${Math.round(number / 1000000)}M`;
      if (number >= 1000) return `${Math.round(number / 1000)}K`;
      return String(number);
    },
    formatDate(value) {
      if (!value) return "";
      return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
    },
    iconForCategory(name) {
      const key = (name || "").toLowerCase();
      if (key.includes("food") || key.includes("groceries") || key.includes("coffee")) return "restaurant";
      if (key.includes("transport")) return "directions_car";
      if (key.includes("bill")) return "lightbulb";
      if (key.includes("health")) return "medication";
      if (key.includes("shopping")) return "shopping_bag";
      if (key.includes("salary") || key.includes("income")) return "work";
      return "category";
    },
    iconTone(index) {
      return ["bg-tertiarySoft text-tertiary", "bg-dangerSoft text-danger", "bg-primarySoft text-primary", "bg-surfaceHigh text-textMuted"][index % 4];
    }
  },
  template: `
    <div v-if="booting" class="login-wrap">
      <div class="card login-card text-center">
        <div class="brand-mark mx-auto mb-5"><span class="material-symbols-outlined">account_balance_wallet</span></div>
        <p class="font-bold text-lg">Loading Personal XP</p>
      </div>
    </div>

    <div v-else-if="!authenticated" class="login-wrap">
      <div class="card login-card">
        <div class="flex flex-col items-center mb-8">
          <div class="brand-mark mb-5 !w-14 !h-14 !rounded-2xl">
            <span class="material-symbols-outlined text-3xl">account_balance_wallet</span>
          </div>
          <h1 class="text-2xl font-extrabold tracking-tight">Personal XP</h1>
          <p class="mt-2 text-sm text-textMuted text-center">Enter the shared PIN to open the spending tracker.</p>
        </div>
        <form class="space-y-5" @submit.prevent="login">
          <div>
            <label class="label-caps block mb-2" for="pin">PIN</label>
            <input id="pin" v-model="loginPin" class="field text-center text-2xl font-bold tracking-[0.25em]" type="password" inputmode="numeric" autocomplete="current-password" required>
          </div>
          <div>
            <label class="label-caps block mb-2" for="actor">Entry Profile</label>
            <select id="actor" v-model="loginActor" class="field">
              <option value="primary">Primary</option>
              <option value="secondary">Secondary</option>
            </select>
          </div>
          <p v-if="loginError" class="text-sm font-semibold text-danger">{{ loginError }}</p>
          <button class="primary-btn w-full" type="submit">
            Unlock
            <span class="material-symbols-outlined text-xl">arrow_forward</span>
          </button>
        </form>
      </div>
    </div>

    <div v-else class="app-shell">
      <div class="mobile-frame">
        <header class="topbar">
          <div class="flex items-center gap-3">
            <div class="brand-mark"><span class="material-symbols-outlined">account_balance_wallet</span></div>
            <div>
              <h1 class="text-xl font-extrabold leading-tight">Personal Tracker</h1>
              <p class="text-xs font-semibold text-textMuted">{{ activeTitle }}</p>
            </div>
          </div>
          <button class="icon-btn" @click="logout" title="Logout">
            <span class="material-symbols-outlined text-3xl">account_circle</span>
          </button>
        </header>

        <main class="content">
          <p v-if="error" class="mb-4 rounded-2xl bg-dangerSoft px-4 py-3 text-sm font-bold text-danger">{{ error }}</p>

          <section v-show="view === 'dashboard'" class="space-y-8">
            <div class="card p-4">
              <div class="flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <p class="label-caps">Monthly Expenses</p>
                  <h2 class="money-display mt-2">{{ formatMoney(totalExpense) }}</h2>
                  <div class="mt-3 inline-flex items-center gap-1 rounded-full bg-primarySoft px-3 py-1 text-sm font-extrabold text-primary">
                    <span class="material-symbols-outlined text-base">trending_up</span>
                    {{ monthlySummary?.transaction_count || 0 }} records
                  </div>
                </div>
                <div class="relative h-28 w-28 shrink-0">
                  <canvas ref="dashboardChart"></canvas>
                  <div class="absolute inset-0 grid place-items-center text-xl font-extrabold text-primaryBright">{{ budgetPercent }}%</div>
                </div>
              </div>
              <div class="mt-6 flex items-center justify-between border-t border-[var(--line)] pt-4">
                <div>
                  <p class="label-caps">Safe To Spend</p>
                  <p class="text-xl font-extrabold">{{ formatMoney(safeToSpend) }}</p>
                </div>
                <button class="primary-btn px-5" @click="setView('budgets')">View Plan</button>
              </div>
            </div>

            <div>
              <div class="mb-3 flex items-center justify-between">
                <h2 class="section-title">Top Categories</h2>
                <button class="text-sm font-extrabold text-primary" @click="setView('reports')">See All</button>
              </div>
              <div class="-mx-5 flex gap-4 overflow-x-auto px-5 py-2">
                <div v-for="(item, index) in topCategories" :key="item.category + item.type" class="card category-tile">
                  <div class="grid h-14 w-14 place-items-center rounded-2xl" :class="iconTone(index)">
                    <span class="material-symbols-outlined text-3xl">{{ iconForCategory(item.category) }}</span>
                  </div>
                  <div class="text-center">
                    <p class="font-extrabold">{{ item.category }}</p>
                    <p class="text-xs font-bold text-textMuted">{{ formatMoney(item.total_idr) }}</p>
                  </div>
                </div>
                <div v-if="!topCategories.length" class="card category-tile text-center text-sm font-semibold text-textMuted">No category spend yet</div>
              </div>
            </div>

            <div>
              <div class="mb-3 flex items-center justify-between">
                <h2 class="section-title">Recent Transactions</h2>
                <button class="icon-btn" @click="setView('transactions')"><span class="material-symbols-outlined">tune</span></button>
              </div>
              <div class="card overflow-hidden">
                <div v-if="!recentTransactions.length" class="empty-state">No transactions yet.</div>
                <div v-for="txn in recentTransactions" :key="txn.id" class="row">
                  <div class="grid h-12 w-12 place-items-center rounded-2xl" :class="txn.type === 'income' ? 'bg-primarySoft text-primary' : 'bg-dangerSoft text-danger'">
                    <span class="material-symbols-outlined">{{ iconForCategory(txn.category) }}</span>
                  </div>
                  <div class="min-w-0">
                    <p class="truncate text-lg font-extrabold">{{ txn.merchant || txn.category || 'Transaction' }}</p>
                    <p class="text-sm text-textMuted">{{ formatDate(txn.txn_date) }} · {{ txn.source_agent }}</p>
                  </div>
                  <p class="text-right text-lg font-extrabold" :class="txn.type === 'income' ? 'amount-income' : 'amount-expense'">
                    {{ txn.type === 'income' ? '+' : '-' }}{{ formatMoney(txn.amount_idr) }}
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section v-show="view === 'transactions'" class="space-y-5">
            <div class="flex items-center justify-between">
              <h2 class="section-title">Transactions</h2>
              <button class="secondary-btn px-4" @click="loadTransactions"><span class="material-symbols-outlined">refresh</span></button>
            </div>
            <div class="card p-4 space-y-3">
              <input v-model="filters.q" class="field" placeholder="Search merchant or category" @change="loadTransactions">
              <div class="grid grid-cols-2 gap-3">
                <select v-model="filters.category_id" class="field" @change="loadTransactions">
                  <option value="">All categories</option>
                  <option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option>
                </select>
                <select v-model="filters.source_agent" class="field" @change="loadTransactions">
                  <option value="">All sources</option>
                  <option value="web">Web</option>
                  <option value="hermes">Hermes</option>
                  <option value="openclaw">OpenClaw</option>
                </select>
              </div>
            </div>
            <div class="card overflow-hidden">
              <div v-if="!transactions.length" class="empty-state">Nothing matches the current filters.</div>
              <div v-for="txn in transactions" :key="txn.id" class="row">
                <div class="grid h-12 w-12 place-items-center rounded-2xl bg-surfaceLow text-primary">
                  <span class="material-symbols-outlined">{{ iconForCategory(txn.category) }}</span>
                </div>
                <div class="min-w-0">
                  <p class="truncate text-base font-extrabold">{{ txn.merchant || txn.category || 'Transaction' }}</p>
                  <p class="text-xs font-semibold text-textMuted">{{ formatDate(txn.txn_date) }} · {{ txn.category || 'Uncategorized' }} · {{ txn.source_agent }}</p>
                </div>
                <div class="text-right">
                  <p class="font-extrabold" :class="txn.type === 'income' ? 'amount-income' : 'amount-expense'">{{ txn.type === 'income' ? '+' : '-' }}{{ formatMoney(txn.amount_idr) }}</p>
                  <button class="mt-1 text-xs font-bold text-danger" @click="deleteTransaction(txn)">Delete</button>
                </div>
              </div>
            </div>
          </section>

          <section v-show="view === 'add'" class="space-y-5">
            <h2 class="section-title">Add Expense</h2>
            <form class="card p-4 space-y-4" @submit.prevent="submitTransaction">
              <div>
                <label class="label-caps block mb-2">Amount</label>
                <input v-model="form.amount" class="field text-2xl font-extrabold" inputmode="decimal" placeholder="0" required>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <select v-model="form.type" class="field">
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                </select>
                <input v-model="form.txn_date" class="field" type="date" required>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <input v-model="form.category" class="field" list="category-list" placeholder="Category">
                <input v-model="form.merchant" class="field" placeholder="Merchant">
              </div>
              <datalist id="category-list">
                <option v-for="category in categories" :key="category.id" :value="category.name"></option>
              </datalist>
              <textarea v-model="form.description" class="field min-h-24" placeholder="Notes"></textarea>
              <div>
                <label class="label-caps block mb-2">Receipt</label>
                <input ref="receiptInput" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp,image/heic" @change="onReceiptChange">
                <div class="flex items-center gap-3">
                  <button class="secondary-btn px-4" type="button" @click="$refs.receiptInput.click()">
                    <span class="material-symbols-outlined">upload_file</span>
                    Choose Receipt
                  </button>
                  <span class="min-w-0 truncate text-sm font-semibold text-textMuted">{{ receiptName || 'No file selected' }}</span>
                </div>
              </div>
              <button class="primary-btn w-full" type="submit">Save Transaction</button>
            </form>
          </section>

          <section v-show="view === 'budgets'" class="space-y-5">
            <h2 class="section-title">Budgets</h2>
            <form class="card p-4 space-y-4" @submit.prevent="submitBudget">
              <select v-model="budgetForm.category_id" class="field" required>
                <option value="">Select category</option>
                <option v-for="category in expenseCategories" :key="category.id" :value="category.id">{{ category.name }}</option>
              </select>
              <div class="grid grid-cols-2 gap-3">
                <input v-model="budgetForm.limit_amount" class="field" inputmode="decimal" placeholder="Limit amount" required>
                <select v-model="budgetForm.period" class="field">
                  <option value="monthly">Monthly</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>
              <input v-model="budgetForm.start_date" class="field" type="date" required>
              <label class="flex items-center gap-3 text-sm font-bold text-textMuted">
                <input v-model="budgetForm.alert_telegram" type="checkbox" class="rounded border-0 text-primary focus:ring-primary">
                Telegram alert
              </label>
              <button class="primary-btn w-full" type="submit">Create Budget</button>
            </form>
            <div class="card overflow-hidden">
              <div v-if="!budgets.length" class="empty-state">No budgets configured yet.</div>
              <div v-for="budget in budgets" :key="budget.id" class="row !grid-cols-[48px_minmax(0,1fr)_auto]">
                <div class="grid h-12 w-12 place-items-center rounded-2xl bg-primarySoft text-primary">
                  <span class="material-symbols-outlined">savings</span>
                </div>
                <div>
                  <p class="font-extrabold">{{ budget.category }}</p>
                  <p class="text-sm text-textMuted">{{ budget.period }} · from {{ formatDate(budget.start_date) }}</p>
                </div>
                <p class="font-extrabold">{{ formatMoney(budget.limit_amount) }}</p>
              </div>
            </div>
          </section>

          <section v-show="view === 'reports'" class="space-y-5">
            <div class="flex items-center justify-between">
              <h2 class="section-title">Reports</h2>
              <button class="secondary-btn px-4" @click="downloadPdf">
                <span class="material-symbols-outlined">picture_as_pdf</span>
                PDF
              </button>
            </div>
            <div class="card p-4">
              <p class="label-caps">Monthly Net</p>
              <p class="money-display mt-2">{{ formatMoney(monthlySummary?.net_idr) }}</p>
              <p class="mt-2 text-sm font-semibold text-textMuted">{{ monthlySummary?.insights?.[0] || 'No insight yet.' }}</p>
            </div>
            <div class="card p-4">
              <div class="mb-4 flex items-center justify-between">
                <p class="font-extrabold">Category Breakdown</p>
                <p class="text-sm font-bold text-textMuted">{{ monthlySummary?.transaction_count || 0 }} records</p>
              </div>
              <div class="chart-box">
                <canvas ref="reportChart"></canvas>
              </div>
            </div>
            <div class="card overflow-hidden">
              <div v-for="item in monthlySummary?.category_totals || []" :key="item.category + item.type" class="row">
                <div class="grid h-12 w-12 place-items-center rounded-2xl bg-surfaceLow text-primary">
                  <span class="material-symbols-outlined">{{ iconForCategory(item.category) }}</span>
                </div>
                <div>
                  <p class="font-extrabold">{{ item.category }}</p>
                  <p class="text-sm text-textMuted">{{ item.count }} transactions</p>
                </div>
                <p class="font-extrabold">{{ formatMoney(item.total_idr) }}</p>
              </div>
            </div>
          </section>
        </main>

        <nav class="bottom-nav">
          <button v-for="tab in tabs" :key="tab.id" class="nav-item" :class="{ active: view === tab.id }" @click="setView(tab.id)">
            <span class="material-symbols-outlined text-2xl">{{ tab.icon }}</span>
            <span>{{ tab.label }}</span>
          </button>
        </nav>
      </div>
    </div>
  `
}).mount("#app");
