"""The MCP-style tools the Command Executor dispatches to: modify-infra,
deploy-service, update-database. Each acts on storage.infra_state, the
K8s/AWS/feature-flag substitute, and returns an ActionResult carrying
before/after state so the caller can post a concrete confirmation."""

from shared.models import ActionRequest, ActionResult
from storage import infra_state


def modify_infra(request: ActionRequest) -> ActionResult:
    before = infra_state.get_resource(request.service)

    if request.replica_count is not None:
        after = infra_state.update_resource(request.service, replica_count=request.replica_count)
        return ActionResult(
            action_type="modify_infra", service=request.service, success=True,
            message=f"Scaled {request.service} to {request.replica_count} replicas.",
            before=before, after=after,
        )

    if request.feature_flag is not None and request.feature_flag_enabled is not None:
        after = infra_state.set_feature_flag(
            request.service, request.feature_flag, request.feature_flag_enabled
        )
        state = "enabled" if request.feature_flag_enabled else "disabled"
        return ActionResult(
            action_type="modify_infra", service=request.service, success=True,
            message=f"{state.capitalize()} feature flag '{request.feature_flag}' on {request.service}.",
            before=before, after=after,
        )

    return ActionResult(
        action_type="modify_infra", service=request.service, success=False,
        message="No replica_count or feature_flag/feature_flag_enabled provided.",
        before=before, after=before,
    )


def deploy_service(request: ActionRequest) -> ActionResult:
    before = infra_state.get_resource(request.service)

    if request.deploy_action == "rollback":
        target_version = before.get("previous_version")
        if not target_version:
            return ActionResult(
                action_type="deploy_service", service=request.service, success=False,
                message=f"No previous_version recorded for {request.service} -- cannot roll back.",
                before=before, after=before,
            )
        after = infra_state.update_resource(
            request.service, deployed_version=target_version,
            previous_version=before.get("deployed_version"),
        )
        return ActionResult(
            action_type="deploy_service", service=request.service, success=True,
            message=f"Rolled back {request.service} from "
                    f"{before.get('deployed_version')} to {target_version}.",
            before=before, after=after,
        )

    if request.deploy_action == "redeploy":
        target_version = request.target_version or before.get("deployed_version")
        after = infra_state.update_resource(
            request.service, deployed_version=target_version,
            previous_version=before.get("deployed_version"),
        )
        return ActionResult(
            action_type="deploy_service", service=request.service, success=True,
            message=f"Redeployed {request.service} to {target_version}.",
            before=before, after=after,
        )

    return ActionResult(
        action_type="deploy_service", service=request.service, success=False,
        message="No deploy_action provided (expected 'rollback' or 'redeploy').",
        before=before, after=before,
    )


def update_database(request: ActionRequest) -> ActionResult:
    before = infra_state.get_resource(request.service)

    if request.connection_pool_size is None:
        return ActionResult(
            action_type="update_database", service=request.service, success=False,
            message="No connection_pool_size provided.", before=before, after=before,
        )

    after = infra_state.update_resource(
        request.service, connection_pool_size=request.connection_pool_size
    )
    return ActionResult(
        action_type="update_database", service=request.service, success=True,
        message=f"Updated {request.service} connection_pool_size to {request.connection_pool_size}.",
        before=before, after=after,
    )


def dispatch(request: ActionRequest) -> ActionResult:
    if request.action_type == "modify_infra":
        return modify_infra(request)
    if request.action_type == "deploy_service":
        return deploy_service(request)
    if request.action_type == "update_database":
        return update_database(request)
    return ActionResult(
        action_type="unrecognized", service=request.service, success=False,
        message="Could not map this instruction to a known action.", before={}, after={},
    )


if __name__ == "__main__":
    infra_state.seed({"checkout-service": {"replica_count": 4, "deployed_version": "v42",
                                            "previous_version": "v41"}})

    result = dispatch(ActionRequest(
        action_type="deploy_service", service="checkout-service",
        instruction_summary="rollback", deploy_action="rollback",
    ))
    print(result)
