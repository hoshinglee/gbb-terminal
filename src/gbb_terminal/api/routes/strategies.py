from __future__ import annotations

import asyncio

from fastapi import APIRouter

from ...llm.translator import GoogleAIStrategyTranslator
from ...storage.database import LocalMarketStore
from ...strategy.catalogue import StrategyCatalogue
from .shared import bad_request
from ..schemas.v2 import StrategyCreateRequest, StrategyProposalV2Request


def create_strategy_router(store: LocalMarketStore, translator: GoogleAIStrategyTranslator, catalogue: StrategyCatalogue) -> APIRouter:
    router = APIRouter(prefix="/api/v2", tags=["Strategy V2"])

    @router.get("/strategy-templates")
    async def templates():
        return {"templates": [template.model_dump(mode="json") for template in catalogue.list_templates()]}

    @router.post("/strategy-proposals")
    async def proposal(request: StrategyProposalV2Request):
        try:
            translation = await asyncio.to_thread(translator.translate, request.instruction)
            strategy = translation.strategy
            return {
                "proposal": {
                    "name": strategy.spec().name,
                    "description": translation.normalized_instruction,
                    "direction": strategy.spec().direction,
                    "ruleGraph": strategy.spec().parameters,
                    "requiredDatasets": ["daily_prices"],
                },
                "clarifications": translation.clarifications,
                "needsConfirmation": translation.needs_confirmation,
                "provider": translation.provider,
                "advanced": {"yaml": translation.yaml_config},
            }
        except ValueError as error:
            raise bad_request(error) from error

    @router.post("/strategies")
    async def create_strategy(request: StrategyCreateRequest):
        try:
            template = catalogue.get(request.strategy.template_id)
            key = request.strategy.semantic_key()
            if catalogue.is_portfolio(request.strategy.template_id):
                definition = {"strategy_type": "ranked_portfolio", "name": request.strategy.name, "description": request.strategy.description, "direction": "long", "parameters": request.strategy.parameter_values}
                strategy_yaml = ""
            else:
                strategy = catalogue.build(request.strategy)
                definition = strategy.spec().to_dict()
                strategy_yaml = strategy.to_yaml()
            saved = store.save_strategy(
                request.original_instruction or request.strategy.description,
                definition,
                "strategy_model_v2",
                strategy_yaml,
                key,
                strategy_json=request.strategy.model_dump(mode="json"),
                family=template.family,
                template_id=template.template_id,
                template_version=template.version,
            )
            return {"strategy": {key: value for key, value in saved.items() if key not in {"key", "strategyYaml"}}}
        except ValueError as error:
            raise bad_request(error) from error

    return router
