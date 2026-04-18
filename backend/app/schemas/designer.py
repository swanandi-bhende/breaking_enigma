from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


class Component(BaseModel):
    component_name: str
    type: Literal["layout", "form", "display", "navigation", "feedback"]
    props: Dict[str, Any] = Field(default_factory=dict)
    state_dependencies: List[str] = Field(default_factory=list)


class Screen(BaseModel):
    screen_id: str
    screen_name: str
    route: str
    purpose: str
    components: List[Component]
    ux_decisions: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    wireframe_description: str


class InteractionFlow(BaseModel):
    flow_id: str
    flow_name: str
    trigger: str
    steps: List[str]
    happy_path_end: str
    failure_paths: List[str] = Field(default_factory=list)


class SystemArchitecture(BaseModel):
    frontend: str
    backend: str
    database: str
    cache: Optional[str] = None
    external_services: List[str] = Field(default_factory=list)
    communication_patterns: Dict[str, str] = Field(default_factory=dict)


class RequestBodySchema(BaseModel):
    content_type: str = "application/json"
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    validation_rules: List[str] = Field(default_factory=list)


class ResponseSchemaItem(BaseModel):
    description: str
    response_schema: Dict[str, Any] = Field(default_factory=dict)
    example: Dict[str, Any] = Field(default_factory=dict)


class APIEndpoint(BaseModel):
    endpoint_id: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    auth_required: bool
    description: str
    request_body: RequestBodySchema = Field(default_factory=RequestBodySchema)
    responses: Dict[str, ResponseSchemaItem] = Field(default_factory=dict)
    rate_limit: Optional[str] = None
    maps_to_user_stories: List[str] = Field(default_factory=list)


class DataModelField(BaseModel):
    name: str
    type: str
    nullable: bool = False
    unique: bool = False
    indexed: bool = False
    foreign_key: Optional[str] = None
    default: Optional[str] = None


class Relationship(BaseModel):
    type: Literal["one-to-one", "one-to-many", "many-to-many"]
    with_entity: str
    foreign_key: str


class DataModel(BaseModel):
    entity_name: str
    table_name: str
    fields: List[DataModelField]
    relationships: List[Relationship] = Field(default_factory=list)


class DesignSpec(BaseModel):
    screens: List[Screen]
    interaction_flows: List[InteractionFlow]
    system_architecture: SystemArchitecture
    api_spec: List[APIEndpoint]
    data_models: List[DataModel]


class DesignerAgentInput(BaseModel):
    run_id: str
    prd: dict
    research_context_embedding_ids: List[str] = Field(default_factory=list)


class DesignerAgentOutput(BaseModel):
    run_id: str
    design_spec: DesignSpec
