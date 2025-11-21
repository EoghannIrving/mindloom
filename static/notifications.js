(() => {
  'use strict';

  const STORAGE_KEY = 'mindloom-reminder-state';
  const MOMENTUM_THRESHOLD_MS = 90 * 60 * 1000;
  const MOMENTUM_SNOOZE_MS = 30 * 60 * 1000;
  const CHECKIN_MIN_DELAY_MS = 20 * 60 * 1000;
  const CHECKIN_MAX_DELAY_MS = 40 * 60 * 1000;
  const COMPLETION_WINDOW_MS = 5 * 60 * 1000;
  const COMPLETION_LIMIT = 2;

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

  const DEFAULT_STATE = {
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
  };

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
      if (!storageAvailable) {
        return { ...DEFAULT_STATE };
      }
      try {
        const raw = window.localStorage.getItem(this.key);
        if (!raw) {
          return { ...DEFAULT_STATE };
        }
        const parsed = JSON.parse(raw);
        const state = {
          ...DEFAULT_STATE,
          ...parsed,
          snoozes: {
            ...DEFAULT_STATE.snoozes,
            ...(parsed.snoozes || {}),
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
        return { ...DEFAULT_STATE };
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
      this.state = {
        ...this.state,
        ...values,
      };
      if (values.snoozes) {
        this.state.snoozes = {
          ...this.state.snoozes,
          ...values.snoozes,
        };
      }
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

  function randomCheckinDelay() {
    const range = CHECKIN_MAX_DELAY_MS - CHECKIN_MIN_DELAY_MS;
    return CHECKIN_MIN_DELAY_MS + Math.floor(Math.random() * range);
  }

  class ReminderController {
    constructor() {
      this.store = new ReminderStore();
      this.state = this.store.state;
      this.ui = {};
      this.swRegistration = null;
      this.toastTimer = null;
    }

    init() {
      this.queryElements();
      this.bindUI();
      this.syncStopForNowToggle();
      this.renderActiveTask();
      this.recordIdleSession();
      this.listenToServiceWorker();
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
      this.ui.snoozeCheckinButton = document.querySelector('[data-snooze-checkin]');
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
        })
        .catch(() => {});
      navigator.serviceWorker.addEventListener('message', (event) => {
        const payload = event.data;
        if (payload && payload.type === 'mindloom-notification-action') {
          this.handleNotificationAction(payload.payload);
        }
      });
    }

    recordIdleSession() {
      const lastEnd = this.state.lastSessionEnded;
      if (lastEnd && Date.now() - lastEnd >= MOMENTUM_THRESHOLD_MS) {
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
      if (forceIdle && sinceRequest < MOMENTUM_THRESHOLD_MS && this.state.lastNextTaskRequest) {
        return;
      }
      if (!forceIdle && sinceRequest < MOMENTUM_THRESHOLD_MS) {
        return;
      }
      const sincePrompt = this.state.lastMomentumPrompt
        ? now - this.state.lastMomentumPrompt
        : Infinity;
      if (sincePrompt < MOMENTUM_THRESHOLD_MS) {
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
      const nextAt = activeTask.checkinNextAt || now + randomCheckinDelay();
      if (now < nextAt) {
        this.updateCheckinHint();
        return;
      }
      const recentNotification = activeTask.lastNotificationAt
        ? now - activeTask.lastNotificationAt
        : Infinity;
      if (recentNotification < CHECKIN_MIN_DELAY_MS) {
        return;
      }
      this.presentCheckinReminder(activeTask);
      this.state.activeTask.lastNotificationAt = now;
      this.state.activeTask.checkinNextAt = now + randomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
      this.renderActiveTask();
    }

    presentMomentumReminder() {
      const message =
        MOMENTUM_MESSAGES[Math.floor(Math.random() * MOMENTUM_MESSAGES.length)];
      this.showNotification('Need a nudge?', {
        body: message,
        tag: 'mindloom-momentum',
        data: { type: 'momentum' },
        actions: [
          { action: 'momentum_next', title: 'Next task' },
          { action: 'momentum_snooze', title: 'Snooze 30m' },
        ],
      });
      this.showInlineToast(message, [
        { label: 'Next task', handler: () => this.launchNextTask() },
        { label: 'Snooze 30m', handler: () => this.snoozeMomentum() },
      ]);
    }

    presentCompletionReminder() {
      const message =
        COMPLETION_MESSAGES[
          Math.floor(Math.random() * COMPLETION_MESSAGES.length)
        ];
      this.state.lastCompletionPrompt = Date.now();
      this.store.save();
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
      const display = () => {
        if (this.swRegistration && this.swRegistration.showNotification) {
          this.swRegistration.showNotification(title, options);
        } else {
          new Notification(title, options);
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
            this.showInlineToast(options.body || title, []);
          }
        });
        return;
      }
      this.showInlineToast(options.body || title, []);
    }

    showInlineToast(message, actions = []) {
      if (!this.ui.reminderToast || !this.ui.reminderToastMessage) {
        return;
      }
      this.ui.reminderToastMessage.textContent = message;
      this.ui.reminderToastActions.innerHTML = '';
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
      }
      this.toastTimer = window.setTimeout(() => {
        this.ui.reminderToast?.classList.add('hidden');
      }, 8000);
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
        checkinNextAt: timestamp + randomCheckinDelay(),
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
        Date.now() + randomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
    }

    scheduleNextCheckin() {
      if (!this.state.activeTask) {
        return;
      }
      this.state.activeTask.checkinNextAt =
        Date.now() + randomCheckinDelay();
      this.store.setActiveTask(this.state.activeTask);
      this.renderActiveTask();
    }

    updateStopForNow(value) {
      this.state.stopForNow = Boolean(value);
      if (this.ui.stopForNowToggle) {
        this.ui.stopForNowToggle.checked = this.state.stopForNow;
      }
      this.store.update({ stopForNow: this.state.stopForNow });
      this.showInlineToast(
        this.state.stopForNow ? 'Reminders paused.' : 'Reminders re-enabled.',
        [],
      );
    }

    snoozeMomentum() {
      const snoozeUntil = Date.now() + MOMENTUM_SNOOZE_MS;
      this.store.update({ snoozes: { momentumUntil: snoozeUntil } });
      this.showInlineToast('Momentum reminder snoozed for 30 minutes.', []);
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
      if (this.ui.stopForNowToggle) {
        this.ui.stopForNowToggle.checked = false;
      }
      this.store.update({
        lastNextTaskRequest: this.state.lastNextTaskRequest,
        stopForNow: this.state.stopForNow,
      });
    }

    recordCompletionEvent(detail = {}) {
      if (!detail.count || detail.count < 1) {
        return;
      }
      const now = Date.now();
      if (
        this.state.lastCompletionPrompt &&
        now - this.state.lastCompletionPrompt < COMPLETION_WINDOW_MS
      ) {
        return;
      }
      this.state.completionRecords = (this.state.completionRecords || [])
        .concat(now)
        .filter((entry) => now - entry < COMPLETION_WINDOW_MS);
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
      }
    }
  }

  const controller = new ReminderController();
  window.mindloomReminderController = controller;
  window.addEventListener('mindloom-next-task-request', controller.recordNextTaskRequest.bind(controller));
  window.addEventListener('mindloom-task-completed', (event) =>
    controller.recordCompletionEvent(event.detail),
  );
  document.addEventListener('DOMContentLoaded', () => controller.init());
})();
