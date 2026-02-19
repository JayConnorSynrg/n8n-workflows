/**
 * State Machine Implementation for Department Provisioning
 *
 * Manages state transitions, validation, rollback, and timeout handling
 */

import { ProvisioningState, StateTransition, ProvisioningJob } from './types';

export class ProvisioningStateMachine {
  private static readonly VALID_TRANSITIONS: Record<ProvisioningState, ProvisioningState[]> = {
    [ProvisioningState.PENDING]: [
      ProvisioningState.VALIDATING,
      ProvisioningState.FAILED
    ],
    [ProvisioningState.VALIDATING]: [
      ProvisioningState.CREATING_DATABASE,
      ProvisioningState.FAILED
    ],
    [ProvisioningState.CREATING_DATABASE]: [
      ProvisioningState.CREATING_OAUTH,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.CREATING_OAUTH]: [
      ProvisioningState.DEPLOYING_CONTAINER,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.DEPLOYING_CONTAINER]: [
      ProvisioningState.DEPLOYING_WORKFLOWS,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.DEPLOYING_WORKFLOWS]: [
      ProvisioningState.CONFIGURING_GATEWAY,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.CONFIGURING_GATEWAY]: [
      ProvisioningState.VALIDATING_DEPLOYMENT,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.VALIDATING_DEPLOYMENT]: [
      ProvisioningState.COMPLETED,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ],
    [ProvisioningState.COMPLETED]: [],
    [ProvisioningState.FAILED]: [ProvisioningState.ROLLING_BACK],
    [ProvisioningState.ROLLING_BACK]: [ProvisioningState.FAILED]
  };

  private static readonly STATE_PROGRESS: Record<ProvisioningState, number> = {
    [ProvisioningState.PENDING]: 0,
    [ProvisioningState.VALIDATING]: 5,
    [ProvisioningState.CREATING_DATABASE]: 20,
    [ProvisioningState.CREATING_OAUTH]: 35,
    [ProvisioningState.DEPLOYING_CONTAINER]: 50,
    [ProvisioningState.DEPLOYING_WORKFLOWS]: 70,
    [ProvisioningState.CONFIGURING_GATEWAY]: 85,
    [ProvisioningState.VALIDATING_DEPLOYMENT]: 95,
    [ProvisioningState.COMPLETED]: 100,
    [ProvisioningState.FAILED]: 0,
    [ProvisioningState.ROLLING_BACK]: 0
  };

  private static readonly MAX_PROVISIONING_TIME_MS = 5 * 60 * 1000; // 5 minutes
  private static readonly STEP_TIMEOUT_MS = 60 * 1000; // 1 minute per step

  private transitions: StateTransition[] = [];

  /**
   * Validate if a state transition is allowed
   */
  canTransition(from: ProvisioningState, to: ProvisioningState): boolean {
    const validTransitions = ProvisioningStateMachine.VALID_TRANSITIONS[from];
    return validTransitions.includes(to);
  }

  /**
   * Transition to a new state with validation
   */
  transition(
    job: ProvisioningJob,
    toState: ProvisioningState,
    reason?: string
  ): ProvisioningJob {
    if (!this.canTransition(job.status, toState)) {
      throw new Error(
        `Invalid state transition: ${job.status} -> ${toState}. ` +
        `Valid transitions: ${ProvisioningStateMachine.VALID_TRANSITIONS[job.status].join(', ')}`
      );
    }

    const transition: StateTransition = {
      from: job.status,
      to: toState,
      timestamp: new Date(),
      reason
    };

    this.transitions.push(transition);

    const updatedJob: ProvisioningJob = {
      ...job,
      status: toState,
      currentStep: this.getStepName(toState),
      logs: [
        ...job.logs,
        `[${new Date().toISOString()}] State transition: ${job.status} -> ${toState}${reason ? ` (${reason})` : ''}`
      ]
    };

    // Update estimated completion if still provisioning
    if (this.isActiveState(toState)) {
      updatedJob.estimatedCompletion = this.calculateEstimatedCompletion(
        updatedJob.startedAt,
        toState
      );
    }

    return updatedJob;
  }

  /**
   * Get progress percentage for current state
   */
  getProgress(state: ProvisioningState): number {
    return ProvisioningStateMachine.STATE_PROGRESS[state];
  }

  /**
   * Check if provisioning has timed out
   */
  hasTimedOut(job: ProvisioningJob): boolean {
    const elapsed = Date.now() - job.startedAt.getTime();
    return elapsed > ProvisioningStateMachine.MAX_PROVISIONING_TIME_MS;
  }

  /**
   * Check if a step has timed out
   */
  hasStepTimedOut(stepStartTime: Date): boolean {
    const elapsed = Date.now() - stepStartTime.getTime();
    return elapsed > ProvisioningStateMachine.STEP_TIMEOUT_MS;
  }

  /**
   * Calculate estimated completion time
   */
  private calculateEstimatedCompletion(startTime: Date, currentState: ProvisioningState): Date {
    const currentProgress = this.getProgress(currentState);
    const elapsed = Date.now() - startTime.getTime();
    const remainingProgress = 100 - currentProgress;
    const estimatedRemaining = (elapsed / currentProgress) * remainingProgress;

    return new Date(Date.now() + estimatedRemaining);
  }

  /**
   * Get human-readable step name
   */
  private getStepName(state: ProvisioningState): string {
    const stepNames: Record<ProvisioningState, string> = {
      [ProvisioningState.PENDING]: 'Pending',
      [ProvisioningState.VALIDATING]: 'Validating configuration',
      [ProvisioningState.CREATING_DATABASE]: 'Creating database schema',
      [ProvisioningState.CREATING_OAUTH]: 'Setting up OAuth credentials',
      [ProvisioningState.DEPLOYING_CONTAINER]: 'Deploying container to Railway',
      [ProvisioningState.DEPLOYING_WORKFLOWS]: 'Deploying n8n workflows',
      [ProvisioningState.CONFIGURING_GATEWAY]: 'Configuring API gateway',
      [ProvisioningState.VALIDATING_DEPLOYMENT]: 'Validating deployment',
      [ProvisioningState.COMPLETED]: 'Completed',
      [ProvisioningState.FAILED]: 'Failed',
      [ProvisioningState.ROLLING_BACK]: 'Rolling back changes'
    };

    return stepNames[state];
  }

  /**
   * Check if state is an active provisioning state
   */
  private isActiveState(state: ProvisioningState): boolean {
    return ![
      ProvisioningState.COMPLETED,
      ProvisioningState.FAILED,
      ProvisioningState.ROLLING_BACK
    ].includes(state);
  }

  /**
   * Get rollback sequence for current state
   */
  getRollbackSequence(currentState: ProvisioningState): ProvisioningState[] {
    const sequence: ProvisioningState[] = [];

    switch (currentState) {
      case ProvisioningState.VALIDATING_DEPLOYMENT:
      case ProvisioningState.CONFIGURING_GATEWAY:
        sequence.push(ProvisioningState.CONFIGURING_GATEWAY);
      // fallthrough
      case ProvisioningState.DEPLOYING_WORKFLOWS:
        sequence.push(ProvisioningState.DEPLOYING_WORKFLOWS);
      // fallthrough
      case ProvisioningState.DEPLOYING_CONTAINER:
        sequence.push(ProvisioningState.DEPLOYING_CONTAINER);
      // fallthrough
      case ProvisioningState.CREATING_OAUTH:
        sequence.push(ProvisioningState.CREATING_OAUTH);
      // fallthrough
      case ProvisioningState.CREATING_DATABASE:
        sequence.push(ProvisioningState.CREATING_DATABASE);
        break;
    }

    return sequence;
  }

  /**
   * Get state history
   */
  getHistory(): StateTransition[] {
    return [...this.transitions];
  }

  /**
   * Reset state machine
   */
  reset(): void {
    this.transitions = [];
  }

  /**
   * Retry logic for transient failures
   */
  shouldRetry(attemptCount: number, maxRetries: number = 3): boolean {
    return attemptCount < maxRetries;
  }

  /**
   * Calculate exponential backoff delay
   */
  calculateBackoffDelay(attemptCount: number, baseDelayMs: number = 1000): number {
    return baseDelayMs * Math.pow(2, attemptCount - 1);
  }
}
