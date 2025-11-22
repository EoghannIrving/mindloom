(() => {
  'use strict';

  const STORAGE_KEY = 'mindloom-reminder-state';
  const COMPLETION_LIMIT = 2;

  const DEFAULT_SETTINGS = {
    momentumThresholdMinutes: 90,
    momentumSnoozeMinutes: 30,
    checkinMinMinutes: 20,
    checkinMaxMinutes: 40,
    completionCooldownMinutes: 5,
  };

  const DEFAULT_ACTIVE_TASK = {
    id: null,
    title: '',
    project: '',
    area: '',
    startedAt: null,
    lastActivityAt: null,
    checkinNextAt: null,
    lastNotificationAt: null,
  };

  function createDefaultState() {
    return {
      lastNextTaskRequest: null,
      lastMomentumPrompt: null,
      lastCompletionPrompt: null,
      completionRecords: [],
      stopForNow: false,
      activeTask: null,
      checkinSnoozedDay: '',
      snoozes: {
        momentumUntil: null,
      },
      lastSessionEnded: null,
      settings: { ...DEFAULT_SETTINGS },
    };
  }

  const MOMENTUM_MESSAGES = [
    'Want to pick up where you left off?',
    'Ready for your next task?',
    'Need a gentle nudge back into motion?',
  ];

  const COMPLETION_MESSAGES = [
    'Nice work! Want another?',
    'Good job — keep going?',
    'Ready for another or taking a break?',
  ];

  const SAMPLE_CONFIGS = {
    gentle: {
      momentumThresholdMinutes: 120,
      momentumSnoozeMinutes: 45,
      checkinMinMinutes: 30,
      checkinMaxMinutes: 60,
      completionCooldownMinutes: 10,
    },
    focused: {
      momentumThresholdMinutes: 45,
      momentumSnoozeMinutes: 20,
      checkinMinMinutes: 15,
      checkinMaxMinutes: 30,
      completionCooldownMinutes: 4,
    },
    sprint: {
      momentumThresholdMinutes: 15,
      momentumSnoozeMinutes: 10,
      checkinMinMinutes: 7,
      checkinMaxMinutes: 18,
      completionCooldownMinutes: 2,
    },
  };

  const storageAvailable = (() => {
    try {
      const key = '__mindloom-test__';
      window.localStorage.setItem(key, '1');
      window.localStorage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  })();

  class ReminderStore {
    constructor() {
      this.key = STORAGE_KEY;
      this.state = this.load();
    }

    load() {
      const defaultState = createDefaultState();
      if (!storageAvailable) {
        return defaultState;
      }
      try {
        const raw = window.localStorage.getItem(this.key);
        if (!raw) {
          return defaultState;
        }
        const parsed = JSON.parse(raw);
        const state = {
          ...defaultState,
          ...parsed,
          snoozes: {
            ...defaultState.snoozes,
            ...(parsed.snoozes || {}),
          },
          settings: {
            ...defaultState.settings,
            ...(parsed.settings || {}),
          },
        };
        if (parsed.activeTask) {
          state.activeTask = {
            ...DEFAULT_ACTIVE_TASK,
            ...parsed.activeTask,
          };
        } else {
          state.activeTask = null;
        }
        if (!Array.isArray(state.completionRecords)) {
          state.completionRecords = [];
        } else {
          state.completionRecords = state.completionRecords
            .map((entry) => Number(entry))
            .filter((entry) => Number.isFinite(entry));
        }
        return state;
      } catch (error) {
        console.warn('Mindloom reminder state load failed:', error);
        return defaultState;
      }
    }

    save() {
      if (!storageAvailable) {
        return;
      }
      try {
        window.localStorage.setItem(this.key, JSON.stringify(this.state));
      } catch (error) {
        console.warn('Mindloom reminder state save failed:', error);
      }
    }

    update(values) {
      const { snoozes, settings, ...rest } = values;
      if (snoozes) {
        this.state.snoozes = {
          ...this.state.snoozes,
          ...snoozes,
        };
      }
      if (settings) {
        this.state.settings = {
          ...this.state.settings,
          ...settings,
        };
      }
      Object.assign(this.state, rest);
      this.save();
      return this.state;
    }

    setActiveTask(task) {
      if (!task) {
        this.state.activeTask = null;
      } else {
        this.state.activeTask = {
          ...DEFAULT_ACTIVE_TASK,
          ...task,
        };
      }
      this.save();
      return this.state.activeTask;
    }

    clearActiveTask() {
      this.state.activeTask = null;
      this.save();
    }
  }

  function formatDuration(ms) {
    if (!Number.isFinite(ms) || ms < 0) {
      return 'just now';
    }
    const minutes = Math.round(ms / 60_000);
    if (minutes < 1) {
      return 'just now';
    }
    if (minutes < 60) {
      return `${minutes}m`;
    }
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    if (remainder) {
      return `${hours}h ${remainder}m`;
    }
    return `${hours}h`;
  }

  function isoDate(timestamp = Date.now()) {
    const date = new Date(timestamp);
    return date.toISOString().slice(0, 10);
  }

  function toMs(minutes) {
    const parsed = Number(minutes);
    if (!Number.isFinite(parsed)) {
      return 0;
    }
    return Math.max(0, parsed) * 60_000;
  }

  function randomCheckinDelay(minMs, maxMs) {
    const low = Math.min(minMs, maxMs);
    const high = Math.max(minMs, maxMs);
    if (high <= low) {
      return Math.max(low, 0);
    }
    return low + Math.floor(Math.random() * (high - low));
  }

  class ReminderController {
    constructor() {
      this.store = new ReminderStore();
      this.state = this.store.state;
      this.ui = {};
      this.swRegistration = null;
      this.toastTimer = null;
      this.initialized = false;
      this.pendingNotifications = [];
    }

    init() {
      this.queryElements();
      this.bindUI();
      this.updateSettingsUI();
      this.syncStopForNowToggle();
      this.renderActiveTask();
      this.recordIdleSession();
      this.listenToServiceWorker();
      this.maybeRequestNotificationPermission();
      this.evaluateReminders(true);
      window.addEventListener('focus', () => this.evaluateReminders());
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
          this.evaluateReminders(true);
        }
      });
      window.addEventListener('beforeunload', () => {
        this.state.lastSessionEnded = Date.now();
        this.store.save();
      });
      this.activeTaskTimer = window.setInterval(() => this.renderActiveTask(), 60_000);
      this.initialized = true;
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('mindloom-reminder-controller-ready', { detail: this }),
        );
      }
    }

    queryElements() {
      this.ui.momentumSnoozeBtn = document.getElementById('momentumSnoozeBtn');
      this.ui.stopForNowToggle = document.getElementById('stopForNowToggle');
      this.ui.activeTaskCard = document.getElementById('activeTaskCard');
      this.ui.activeTaskTitle = document.getElementById('activeTaskTitle');
      this.ui.activeTaskMeta = document.getElementById('activeTaskMeta');
      this.ui.activeTaskCheckinHint = document.getElementById('activeTaskCheckinHint');
      this.ui.reminderToast = document.getElementById('reminderToast');
      this.ui.reminderToastMessage = document.getElementById('reminderToastMessage');
      this.ui.reminderToastActions = document.getElementById('reminderToastActions');
      this.ui.reminderToastClose = document.getElementById('reminderToastClose');
      this.ui.snoozeCheckinButton = document.querySelector('[data-snooze-checkin]');
      this.ui.settingInputs = Array.from(
        document.querySelectorAll('[data-reminder-setting]'),
      );
    }

    bindUI() {
      if (this.ui.momentumSnoozeBtn) {
        this.ui.momentumSnoozeBtn.addEventListener('click', () => this.snoozeMomentum());
      }
      if (this.ui.stopForNowToggle) {
        this.ui.stopForNowToggle.addEventListener('change', (event) => {
          this.updateStopForNow(Boolean(event.target.checked));
        });
      }
      if (this.ui.snoozeCheckinButton) {
        this.ui.snoozeCheckinButton.addEventListener('click', () => this.snoozeCheckinsForToday());
      }
      document.querySelectorAll('[data-start-active-task]').forEach((button) => {
        button.addEventListener('click', () => this.setActiveTaskFromElement(button));
      });
      document.querySelectorAll('[data-active-task-action]').forEach((button) => {
        button.addEventListener('click', () => {
          const action = button.dataset.activeTaskAction;
          if (action) {
            this.handleActiveTaskAction(action);
          }
        });
      });
      this.bindSettingControls();
      if (this.ui.reminderToastClose) {
        this.ui.reminderToastClose.addEventListener('click', () => this.hideInlineToast());
      }
    }

    bindSettingControls() {
      if (!this.ui.settingInputs) {
        return;
      }
      this.ui.settingInputs.forEach((input) => {
        input.addEventListener('change', () => this.handleSettingChange(input));
      });
    }

    handleSettingChange(input) {
      const key = input.dataset.reminderSetting;
      if (!key) {
        return;
      }
      const parsed = Number.parseFloat(input.value);
      if (!Number.isFinite(parsed) || parsed < 0) {
        input.value = String(this.getSettingMinutes(key));
        return;
      }
      this.state.settings = {
        ...this.state.settings,
        [key]: parsed,
      };
      this.store.update({ settings: { [key]: parsed } });
      this.updateSettingsUI();
      this.evaluateReminders(true);
    }

    applySampleConfig(button) {
      const key = button?.dataset?.sampleConfig;
      if (!key) {
        return;
      }
      const config = SAMPLE_CONFIGS[key];
      if (!config) {
        return;
      }
      const label = button.dataset.sampleConfigLabel || key;
      this.state.settings = {
        ...this.state.settings,
        ...config,
      };
      this.store.update({ settings: this.state.settings });
      this.updateSettingsUI();
      this.evaluateReminders(true);
      this.showInlineToast(`Applied ${label}.`, []);
    }

    updateSettingsUI() {
      if (!this.ui.settingInputs) {
        return;
      }
      const settings = {
        ...DEFAULT_SETTINGS,
        ...(this.state.settings || {}),
      };
      this.ui.settingInputs.forEach((input) => {
        const key = input.dataset.reminderSetting;
        if (!key) {
          return;
        }
        const value = settings[key];
        if (typeof value !== 'undefined') {
          input.value = String(value);
        }
      });
    }

    syncStopForNowToggle() {
      if (this.ui.stopForNowToggle) {
        this.ui.stopForNowToggle.checked = Boolean(this.state.stopForNow);
      }
    }

    listenToServiceWorker() {
      if (!('serviceWorker' in navigator)) {
        return;
      }
      navigator.serviceWorker.ready
        .then((registration) => {
          this.swRegistration = registration;
          this.flushPendingNotifications();
        })
        .catch(() => {});
      navigator.serviceWorker.addEventListener('message', (event) => {
        const payload = event.data;
        if (payload && payload.type === 'mindloom-notification-action') {
          this.handleNotificationAction(payload.payload);
        }
      });
    }

    maybeRequestNotificationPermission() {
      if (!('Notification' in window)) {
        return;
      }
      if (Notification.permission === 'default') {
        Notification.requestPermission().then((permission) => {
          if (permission === 'denied') {
            this.showInlineToast(
              'Notifications are disabled. Allow them in your browser settings to see reminders outside the app.',
              [],
            );
          }
        });
      }
    }

    recordIdleSession() {
      const lastEnd = this.state.lastSessionEnded;
      const threshold = this.getSettingMs('momentumThresholdMinutes');
      if (lastEnd && threshold && Date.now() - lastEnd >= threshold) {
        this.maybeShowMomentum(true);
      }
      this.state.lastSessionEnded = null;
      this.store.save();
    }

    evaluateReminders(forceIdle = false) {
      this.resetDailySnooze();
      this.maybeShowMomentum(forceIdle);
      this.maybeShowCheckin();
    }

    maybeShowMomentum(forceIdle) {
      if (this.state.stopForNow || this.state.activeTask) {
        return;
      }
      const now = Date.now();
      const threshold = this.getSettingMs('momentumThresholdMinutes');
      const sinceRequest = this.state.lastNextTaskRequest
        ? now - this.state.lastNextTaskRequest
        : Infinity;
      const snoozeUntil = this.state.snoozes?.momentumUntil || 0;
      if (now < snoozeUntil) {
        return;
      }
      if (!this.state.lastNextTaskRequest && !forceIdle) {
        return;
      }
      if (threshold && forceIdle && sinceRequest < threshold && this.state.lastNextTaskRequest) {
        return;
      }
      if (threshold && !forceIdle && sinceRequest < threshold) {
        return;
      }
      const sincePrompt = this.state.lastMomentumPrompt
        ? now - this.state.lastMomentumPrompt
        : Infinity;
      if (threshold && sincePrompt < threshold) {
        return;
      }
      this.presentMomentumReminder();
      this.state.lastMomentumPrompt = now;
      this.store.save();
    }

    maybeShowCheckin() {
      const activeTask = this.state.activeTask;
      if (!activeTask || this.state.stopForNow) {
        return;
      }
      const todayKey = isoDate();
      if (this.state.checkinSnoozedDay === todayKey) {
        this.updateCheckinHint();
        return;
      }
      const now = Date.now();
      const nextAt = activeTask.checkinNextAt || now + this.getRandomCheckinDelay();
      if (now < nextAt) {
        this.updateCheckinHint();
        return;
      }
      const recentNotification = activeTask.lastNotificationAt
        ? now - activeTask.lastNotificationAt
        : Infinity;
      const minDelay = this.getSettingMs('checkinMinMinutes');
      if (minDelay && recentNotification < minDelay) {
        return;
      }
      this.presentCheckinReminder(activeTask);
      this.state.activeTask.lastNotificationAt = now;
      this.state.activeTask.checkinNextAt = now + this.getRandomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
      this.renderActiveTask();
    }

    presentMomentumReminder() {
      const message =
        MOMENTUM_MESSAGES[Math.floor(Math.random() * MOMENTUM_MESSAGES.length)];
      const snoozeMinutes = Math.max(
        1,
        Math.round(this.getSettingMinutes('momentumSnoozeMinutes')),
      );
      const snoozeLabel = `Snooze ${snoozeMinutes}m`;
      this.showNotification('Need a nudge?', {
        body: message,
        tag: 'mindloom-momentum',
        data: { type: 'momentum' },
        actions: [
          { action: 'momentum_next', title: 'Next task' },
          { action: 'momentum_snooze', title: snoozeLabel },
        ],
      });
      this.showInlineToast(message, [
        { label: 'Next task', handler: () => this.launchNextTask() },
        { label: snoozeLabel, handler: () => this.snoozeMomentum() },
      ]);
    }

    presentCompletionReminder() {
      const message =
        COMPLETION_MESSAGES[
          Math.floor(Math.random() * COMPLETION_MESSAGES.length)
        ];
      const now = Date.now();
      this.state.lastCompletionPrompt = now;
      this.store.update({ lastCompletionPrompt: now });
      this.showNotification('Nice work!', {
        body: message,
        tag: 'mindloom-completion',
        data: { type: 'completion' },
        actions: [
          { action: 'completion_next', title: 'Next task' },
          { action: 'completion_stop', title: 'Stop for now' },
        ],
      });
      this.showInlineToast(message, [
        { label: 'Next task', handler: () => this.launchNextTask() },
        { label: 'Stop for now', handler: () => this.updateStopForNow(true) },
      ]);
    }

    presentCheckinReminder(task) {
      const title = task.title || 'Current focus';
      const body = `Still working on ${title}?`;
      this.showNotification('Check in', {
        body,
        tag: 'mindloom-checkin',
        data: { type: 'checkin', taskId: task.id },
        actions: [
          { action: 'checkin_done', title: 'Done' },
          { action: 'checkin_still', title: 'Still going' },
          { action: 'checkin_switch', title: 'Switch' },
          { action: 'checkin_stop', title: 'Stop' },
        ],
      });
      this.showInlineToast(body, [
        { label: 'Done', handler: () => this.handleActiveTaskAction('done') },
        { label: 'Still going', handler: () => this.handleActiveTaskAction('still-going') },
      ]);
    }

    showNotification(title, options) {
      if (!('Notification' in window)) {
        this.showInlineToast(options.body || title, []);
        return;
      }
      const payload = { ...options };
      const requiresServiceWorker =
        Array.isArray(payload.actions) && payload.actions.length > 0;
      const display = () => {
        if (requiresServiceWorker) {
          if (this.swRegistration && this.swRegistration.showNotification) {
            this.swRegistration.showNotification(title, payload);
          } else {
            this.pendingNotifications.push({ title, options: payload });
          }
          return;
        }
        if (this.swRegistration && this.swRegistration.showNotification) {
          this.swRegistration.showNotification(title, payload);
        } else {
          new Notification(title, payload);
        }
      };
      if (Notification.permission === 'granted') {
        display();
        return;
      }
      if (Notification.permission !== 'denied') {
        Notification.requestPermission().then((permission) => {
          if (permission === 'granted') {
            display();
          } else {
            this.showInlineToast(payload.body || title, []);
          }
        });
        return;
      }
      this.showInlineToast(payload.body || title, []);
    }

    flushPendingNotifications() {
      if (!this.swRegistration || !this.pendingNotifications.length) {
        return;
      }
      while (this.pendingNotifications.length) {
        const { title, options } = this.pendingNotifications.shift();
        this.swRegistration.showNotification(title, options);
      }
    }

    showInlineToast(message, actions = []) {
      if (!this.ui.reminderToast || !this.ui.reminderToastMessage) {
        return;
      }
      this.ui.reminderToastMessage.textContent = message;
      this.ui.reminderToastActions.innerHTML = '';
      if (this.ui.reminderToastClose) {
        this.ui.reminderToastClose.classList.remove('hidden');
      }
      actions.forEach(({ label, handler }) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.className =
          'rounded-full border border-indigo-300 bg-white px-3 py-1 text-xs font-semibold text-indigo-800 transition hover:bg-indigo-100';
        button.addEventListener('click', (event) => {
          event.preventDefault();
          handler();
        });
        this.ui.reminderToastActions.appendChild(button);
      });
      this.ui.reminderToast.classList.remove('hidden');
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = null;
      }
      const duration = actions.length === 0 ? 15000 : 0;
      if (duration > 0) {
        this.toastTimer = window.setTimeout(() => {
          this.hideInlineToast();
        }, duration);
      }
    }

    hideInlineToast() {
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
        this.toastTimer = null;
      }
      if (this.ui.reminderToast) {
        this.ui.reminderToast.classList.add('hidden');
      }
      if (this.ui.reminderToastClose) {
        this.ui.reminderToastClose.classList.add('hidden');
      }
    }

    handleNotificationAction(payload) {
      if (!payload || !payload.type) {
        return;
      }
      switch (payload.type) {
        case 'momentum':
          if (payload.action === 'momentum_snooze') {
            this.snoozeMomentum();
          } else {
            this.launchNextTask();
          }
          break;
        case 'completion':
          if (payload.action === 'completion_stop') {
            this.updateStopForNow(true);
          } else {
            this.launchNextTask();
          }
          break;
        case 'checkin':
          this.handleActiveTaskAction(payload.action || 'done');
          break;
        default:
          break;
      }
    }

    handleActiveTaskAction(action) {
      switch (action) {
        case 'done':
          this.completeActiveTask();
          break;
        case 'still-going':
          this.touchActiveTask();
          this.scheduleNextCheckin();
          this.showInlineToast('Great! Keeping the timer updated.', []);
          break;
        case 'switch':
          this.launchNextTask(true);
          break;
        case 'stop':
          this.updateStopForNow(true);
          this.clearActiveTaskState();
          break;
        default:
          break;
      }
    }

    completeActiveTask() {
      const activeTask = this.state.activeTask;
      if (!activeTask || !activeTask.id) {
        this.clearActiveTaskState();
        return;
      }
      this.recordCompletionEvent({ count: 1 });
      this.clearActiveTaskState();
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = '/daily-tasks';
      form.style.display = 'none';
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'task_id';
      input.value = String(activeTask.id);
      form.appendChild(input);
      document.body.appendChild(form);
      form.submit();
    }

    clearActiveTaskState() {
      this.store.clearActiveTask();
      this.state.activeTask = null;
      this.renderActiveTask();
    }

    setActiveTaskFromElement(element) {
      const idValue = element.dataset.taskId;
      const title = element.dataset.taskTitle || 'Active task';
      const project = element.dataset.taskProject || '';
      const area = element.dataset.taskArea || '';
      const parsedId = Number.isFinite(Number(idValue)) ? Number(idValue) : idValue;
      this.setActiveTask({
        id: parsedId,
        title,
        project,
        area,
      });
    }

    setActiveTask(task) {
      const timestamp = Date.now();
      const payload = {
        ...task,
        startedAt: timestamp,
        lastActivityAt: timestamp,
        checkinNextAt: timestamp + this.getRandomCheckinDelay(),
        lastNotificationAt: null,
      };
      this.state.activeTask = this.store.setActiveTask(payload);
      this.state.stopForNow = false;
      if (this.ui.stopForNowToggle) {
        this.ui.stopForNowToggle.checked = false;
      }
      this.renderActiveTask();
    }

    setActiveTaskFromPayload(task) {
      if (!task) {
        return;
      }
      this.setActiveTask({
        id: task.id,
        title: task.title || 'Next task',
        project: task.project || '',
        area: task.area || '',
      });
    }

    touchActiveTask() {
      if (!this.state.activeTask) {
        return;
      }
      this.state.activeTask.lastActivityAt = Date.now();
      this.state.activeTask.checkinNextAt =
        Date.now() + this.getRandomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
    }

    scheduleNextCheckin() {
      if (!this.state.activeTask) {
        return;
      }
      this.state.activeTask.checkinNextAt =
        Date.now() + this.getRandomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
      this.renderActiveTask();
    }

    updateStopForNow(value) {
      this.state.stopForNow = Boolean(value);
      this.store.update({ stopForNow: this.state.stopForNow });
      this.syncStopForNowToggle();
      this.showInlineToast(
        this.state.stopForNow ? 'Reminders paused.' : 'Reminders re-enabled.',
        [],
      );
    }

    snoozeMomentum() {
      const snoozeMs = this.getSettingMs('momentumSnoozeMinutes');
      const snoozeMinutes = Math.max(
        1,
        Math.round(this.getSettingMinutes('momentumSnoozeMinutes')),
      );
      const snoozeUntil = Date.now() + snoozeMs;
      this.store.update({ snoozes: { momentumUntil: snoozeUntil } });
      this.showInlineToast(`Momentum reminder snoozed for ${snoozeMinutes} minutes.`, []);
    }

    snoozeCheckinsForToday() {
      const todayKey = isoDate();
      this.store.update({ checkinSnoozedDay: todayKey });
      this.updateCheckinHint();
      this.showInlineToast('Check-ins snoozed for the rest of the day.', []);
    }

    updateCheckinHint() {
      if (!this.ui.activeTaskCheckinHint) {
        return;
      }
      const task = this.state.activeTask;
      if (!task) {
        this.ui.activeTaskCheckinHint.textContent = '';
        return;
      }
      const todayKey = isoDate();
      if (this.state.checkinSnoozedDay === todayKey) {
        this.ui.activeTaskCheckinHint.textContent = 'Check-ins are snoozed for today.';
        return;
      }
      const now = Date.now();
      const nextAt = task.checkinNextAt || now;
      const remaining = nextAt - now;
      if (remaining <= 0) {
        this.ui.activeTaskCheckinHint.textContent = 'Check-in is pending — tap a status.';
        return;
      }
      this.ui.activeTaskCheckinHint.textContent = `Next check-in in ${formatDuration(
        remaining,
      )}`;
    }

    renderActiveTask() {
      if (!this.ui.activeTaskCard || !this.state.activeTask) {
        this.ui.activeTaskCard?.classList.add('hidden');
        return;
      }
      this.ui.activeTaskCard.classList.remove('hidden');
      this.ui.activeTaskTitle.textContent = this.state.activeTask.title || 'Active task';
      const projectLine =
        this.state.activeTask.project ||
        this.state.activeTask.area ||
        'your focus';
      const startAt = this.state.activeTask.startedAt || Date.now();
      const elapsed = formatDuration(Date.now() - startAt);
      if (this.ui.activeTaskMeta) {
        this.ui.activeTaskMeta.textContent = `Working on ${projectLine} · started ${elapsed} ago`;
      }
      this.updateCheckinHint();
    }

    launchNextTask(focus = false) {
      if (typeof window.requestPlan !== 'function') {
        this.showInlineToast(
          'Ask for the next task from the planner to continue.',
          [],
        );
        return;
      }
      window
        .requestPlan('next_task')
        .then((data) => {
          if (focus && data && data.next_task) {
            this.setActiveTaskFromPayload(data.next_task);
          }
        })
        .catch(() => {
          this.showInlineToast('Unable to request the next task right now.', []);
        });
    }

    recordNextTaskRequest() {
      this.state.lastNextTaskRequest = Date.now();
      this.state.stopForNow = false;
      this.store.update({
        lastNextTaskRequest: this.state.lastNextTaskRequest,
        stopForNow: this.state.stopForNow,
      });
      this.syncStopForNowToggle();
    }

    recordCompletionEvent(detail = {}) {
      if (!detail.count || detail.count < 1) {
        return;
      }
      const now = Date.now();
      const cooldownMs = this.getSettingMs('completionCooldownMinutes');
      if (
        this.state.lastCompletionPrompt &&
        cooldownMs &&
        now - this.state.lastCompletionPrompt < cooldownMs
      ) {
        return;
      }
      const retention = cooldownMs || 1;
      this.state.completionRecords = (this.state.completionRecords || [])
        .concat(now)
        .filter((entry) => now - entry < retention);
      this.store.update({
        completionRecords: this.state.completionRecords,
      });
      if (
        !this.state.stopForNow &&
        this.state.completionRecords.length <= COMPLETION_LIMIT
      ) {
        this.presentCompletionReminder();
      }
    }

    resetDailySnooze() {
      if (
        this.state.checkinSnoozedDay &&
        this.state.checkinSnoozedDay !== isoDate()
      ) {
        this.store.update({ checkinSnoozedDay: '' });
        this.state.checkinSnoozedDay = '';
      }
    }

    getSettingMinutes(key) {
      const candidate = this.state.settings?.[key];
      if (Number.isFinite(Number(candidate)) && candidate >= 0) {
        return Number(candidate);
      }
      return DEFAULT_SETTINGS[key];
    }

    getSettingMs(key) {
      const minutes = this.getSettingMinutes(key);
      return toMs(minutes);
    }

    getRandomCheckinDelay() {
      const minMs = this.getSettingMs('checkinMinMinutes');
      const maxMs = this.getSettingMs('checkinMaxMinutes');
      return randomCheckinDelay(minMs, maxMs);
    }
  }

  const controller = new ReminderController();
  window.mindloomReminderController = controller;
  window.addEventListener('mindloom-next-task-request', controller.recordNextTaskRequest.bind(controller));
  window.addEventListener('mindloom-task-completed', (event) =>
    controller.recordCompletionEvent(event.detail),
  );
  const ensureControllerReady = (callback) => {
    if (typeof callback !== 'function') {
      return;
    }
    if (controller.initialized) {
      callback();
      return;
    }
    const handler = () => {
      callback();
      window.removeEventListener('mindloom-reminder-controller-ready', handler);
    };
    window.addEventListener('mindloom-reminder-controller-ready', handler);
  };
  window.applyReminderSampleConfig = (button) => {
    ensureControllerReady(() => controller.applySampleConfig(button));
  };
  document.addEventListener('DOMContentLoaded', () => controller.init());
})();
