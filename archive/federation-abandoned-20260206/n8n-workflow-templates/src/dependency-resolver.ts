/**
 * N8N Workflow Dependency Resolver
 * Version: 1.0.0
 *
 * Resolves workflow import order using topological sort.
 * Ensures workflows are deployed in the correct order (dependencies first).
 */

import {
  WorkflowDependency,
  DependencyGraph,
  CircularDependencyError,
  WorkflowTemplate
} from './types';

export class DependencyResolver {
  /**
   * Resolve dependencies and return workflows in deployment order
   * Uses Kahn's algorithm for topological sort
   */
  resolveDependencies(workflows: WorkflowDependency[]): string[] {
    const graph = this.buildDependencyGraph(workflows);
    return this.topologicalSort(graph);
  }

  /**
   * Build dependency graph from workflow dependencies
   */
  private buildDependencyGraph(workflows: WorkflowDependency[]): DependencyGraph {
    const nodes = new Map<string, string[]>();
    const inDegree = new Map<string, number>();

    // Initialize all workflow IDs
    workflows.forEach(wf => {
      nodes.set(wf.workflowId, wf.dependsOn);
      inDegree.set(wf.workflowId, wf.dependsOn.length);

      // Ensure all dependencies are tracked
      wf.dependsOn.forEach(dep => {
        if (!inDegree.has(dep)) {
          inDegree.set(dep, 0);
          nodes.set(dep, []);
        }
      });
    });

    return { nodes, inDegree };
  }

  /**
   * Topological sort using Kahn's algorithm
   */
  private topologicalSort(graph: DependencyGraph): string[] {
    const { nodes, inDegree } = graph;
    const sorted: string[] = [];
    const queue: string[] = [];

    // Find all nodes with no dependencies (in-degree = 0)
    inDegree.forEach((degree, id) => {
      if (degree === 0) {
        queue.push(id);
      }
    });

    // Process queue
    while (queue.length > 0) {
      const current = queue.shift()!;
      sorted.push(current);

      // Find workflows that depend on current
      nodes.forEach((dependencies, workflowId) => {
        if (dependencies.includes(current)) {
          const newDegree = inDegree.get(workflowId)! - 1;
          inDegree.set(workflowId, newDegree);

          if (newDegree === 0) {
            queue.push(workflowId);
          }
        }
      });
    }

    // Check for circular dependencies
    if (sorted.length !== nodes.size) {
      const remaining = Array.from(nodes.keys()).filter(id => !sorted.includes(id));
      const cycle = this.findCycle(graph, remaining);
      throw new CircularDependencyError(
        `Circular dependency detected: ${cycle.join(' -> ')}`,
        cycle
      );
    }

    return sorted;
  }

  /**
   * Find a cycle in the dependency graph (for error reporting)
   */
  private findCycle(graph: DependencyGraph, remaining: string[]): string[] {
    const visited = new Set<string>();
    const recStack = new Set<string>();
    const cycle: string[] = [];

    const dfs = (node: string): boolean => {
      if (recStack.has(node)) {
        // Found cycle
        cycle.push(node);
        return true;
      }

      if (visited.has(node)) {
        return false;
      }

      visited.add(node);
      recStack.add(node);

      const dependencies = graph.nodes.get(node) || [];
      for (const dep of dependencies) {
        if (dfs(dep)) {
          if (cycle[0] !== node) {
            cycle.unshift(node);
          }
          return true;
        }
      }

      recStack.delete(node);
      return false;
    };

    for (const node of remaining) {
      if (dfs(node)) {
        return cycle;
      }
    }

    return remaining; // Fallback if DFS doesn't find cycle
  }

  /**
   * Validate dependency graph (no missing dependencies)
   */
  validateDependencies(workflows: WorkflowDependency[]): {
    valid: boolean;
    missingDependencies: string[];
  } {
    const allWorkflowIds = new Set(workflows.map(w => w.workflowId));
    const missingDependencies: string[] = [];

    workflows.forEach(wf => {
      wf.dependsOn.forEach(dep => {
        if (!allWorkflowIds.has(dep)) {
          missingDependencies.push(`${wf.workflowId} depends on missing workflow: ${dep}`);
        }
      });
    });

    return {
      valid: missingDependencies.length === 0,
      missingDependencies
    };
  }

  /**
   * Extract dependencies from workflow templates
   */
  extractDependenciesFromTemplates(templates: WorkflowTemplate[]): WorkflowDependency[] {
    return templates.map(template => ({
      workflowId: template.id,
      dependsOn: template.meta.dependencies
    }));
  }

  /**
   * Group workflows into deployment batches (parallel deployment)
   * Workflows in the same batch have no dependencies on each other
   */
  groupIntoBatches(workflows: WorkflowDependency[]): string[][] {
    const graph = this.buildDependencyGraph(workflows);
    const batches: string[][] = [];
    const processed = new Set<string>();

    while (processed.size < graph.nodes.size) {
      const batch: string[] = [];

      // Find all workflows whose dependencies are already processed
      graph.inDegree.forEach((degree, workflowId) => {
        if (processed.has(workflowId)) {
          return; // Already processed
        }

        const dependencies = graph.nodes.get(workflowId) || [];
        const allDepsProcessed = dependencies.every(dep => processed.has(dep));

        if (allDepsProcessed) {
          batch.push(workflowId);
        }
      });

      if (batch.length === 0) {
        // No progress - circular dependency
        const remaining = Array.from(graph.nodes.keys()).filter(id => !processed.has(id));
        const cycle = this.findCycle(graph, remaining);
        throw new CircularDependencyError(
          `Circular dependency detected: ${cycle.join(' -> ')}`,
          cycle
        );
      }

      batches.push(batch);
      batch.forEach(id => processed.add(id));
    }

    return batches;
  }
}

/**
 * Utility function for quick dependency resolution
 */
export function resolveWorkflowOrder(workflows: WorkflowDependency[]): string[] {
  const resolver = new DependencyResolver();
  return resolver.resolveDependencies(workflows);
}

/**
 * Utility function for batch resolution
 */
export function resolveBatches(workflows: WorkflowDependency[]): string[][] {
  const resolver = new DependencyResolver();
  return resolver.groupIntoBatches(workflows);
}

/**
 * Example usage:
 *
 * const workflows = [
 *   { workflowId: 'teams-voice-bot', dependsOn: ['gmail-subworkflow'] },
 *   { workflowId: 'gmail-subworkflow', dependsOn: [] },
 *   { workflowId: 'google-drive-repo', dependsOn: [] }
 * ];
 *
 * const resolver = new DependencyResolver();
 * const order = resolver.resolveDependencies(workflows);
 * // Result: ['gmail-subworkflow', 'google-drive-repo', 'teams-voice-bot']
 *
 * const batches = resolver.groupIntoBatches(workflows);
 * // Result: [
 * //   ['gmail-subworkflow', 'google-drive-repo'],  // Batch 1 (no dependencies)
 * //   ['teams-voice-bot']                          // Batch 2 (depends on gmail-subworkflow)
 * // ]
 */
