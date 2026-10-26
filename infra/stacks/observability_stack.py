"""CloudWatch dashboard + alarms on VisionDoctor EMF metrics (docs/05 §5), budget alarm."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cwa
from constructs import Construct

from stacks.app_stack import AppStack
from stacks.compute_stack import CoolComputeStack
from stacks.data_stack import DataStack

NS = "VisionDoctor"


def m(name: str, stat: str = "Sum", **dims: str) -> cw.Metric:
    return cw.Metric(namespace=NS, metric_name=name, statistic=stat, dimensions_map=dims or None,
                     period=cdk.Duration.minutes(5))


class ObservabilityStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, data: DataStack, compute: CoolComputeStack,
                 app_stack: AppStack, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        action = cwa.SnsAction(app_stack.topic)
        alarms = [
            cw.Alarm(self, "DlqDepth", metric=data.dlq.metric_approximate_number_of_messages_visible(),
                     threshold=0, comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD, evaluation_periods=1),
            cw.Alarm(self, "ScanP95", metric=m("ScanLatencyMs", "p95", is_cool="true"), threshold=2000, evaluation_periods=3),
            cw.Alarm(self, "GuardBlocks", metric=m("GuardBlocks"), threshold=10, evaluation_periods=1),
            cw.Alarm(self, "BedrockThrottles", metric=cw.Metric(namespace="AWS/Bedrock", metric_name="InvocationThrottles",
                                                               statistic="Sum", period=cdk.Duration.minutes(5)),
                     threshold=5, evaluation_periods=1),
            cw.Alarm(self, "AsgAtMax", metric=cw.Metric(namespace="AWS/AutoScaling", metric_name="GroupInServiceInstances",
                                                       dimensions_map={"AutoScalingGroupName": compute.workers.auto_scaling_group_name},
                                                       statistic="Maximum", period=cdk.Duration.minutes(5)),
                     threshold=6, comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                     evaluation_periods=3),
        ]
        for a in alarms:
            a.add_alarm_action(action)
        dash = cw.Dashboard(self, "Dash", dashboard_name="VisionDoctor")
        dash.add_widgets(
            cw.GraphWidget(title="Fleet health", left=[m(f"Cameras{s}", "Average") for s in ("Healthy", "Watch", "Degraded", "Failed")]),
            cw.GraphWidget(title="Predicted fleet accuracy", left=[m("PredictedFleetAccuracy", "Average")]),
            cw.GraphWidget(title="Incident funnel", left=[m("IncidentsOpened"), m("AutoFixed"), m("Escalated"), m("FalseAlarm")]),
        )
        dash.add_widgets(
            cw.GraphWidget(title="Scan latency on COOL (ms)", left=[m("ScanLatencyMs", "p50", is_cool="true"),
                                                                   m("ScanLatencyMs", "p95", is_cool="true")]),
            cw.GraphWidget(title="Agent", left=[m("AgentSteps", "Average"), m("GuardBlocks")], right=[m("AgentTokens")]),
            cw.GraphWidget(title="Repair verified rate", left=[m("RepairVerifiedRate", "Average")]),
        )
        budgets.CfnBudget(self, "Budget", budget=budgets.CfnBudget.BudgetDataProperty(
            budget_type="COST", time_unit="MONTHLY",
            budget_limit=budgets.CfnBudget.SpendProperty(amount=50, unit="USD")),
            notifications_with_subscribers=[budgets.CfnBudget.NotificationWithSubscribersProperty(
                notification=budgets.CfnBudget.NotificationProperty(comparison_operator="GREATER_THAN",
                                                                    notification_type="ACTUAL", threshold=80),
                subscribers=[budgets.CfnBudget.SubscriberProperty(subscription_type="SNS",
                                                                  address=app_stack.topic.topic_arn)])])
