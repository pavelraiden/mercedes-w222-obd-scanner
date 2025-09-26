"""
Advanced AI Prompt Optimization System for Mercedes W222 OBD Scanner.
Implements prompt engineering best practices with context-aware templates.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re
from datetime import datetime
import hashlib

class PromptType(Enum):
    """Types of AI prompts in the system."""
    DIAGNOSTIC_ANALYSIS = "diagnostic_analysis"
    TRIP_ANALYSIS = "trip_analysis"
    PREDICTIVE_MAINTENANCE = "predictive_maintenance"
    ERROR_EXPLANATION = "error_explanation"
    RECOMMENDATION = "recommendation"
    SAFETY_ASSESSMENT = "safety_assessment"

class AIProvider(Enum):
    """Supported AI providers."""
    CLAUDE = "claude"
    GPT4 = "gpt4"
    GEMINI = "gemini"

@dataclass
class VehicleContext:
    """Vehicle-specific context for prompts."""
    model: str = "W222"
    year: int = 2020
    engine_type: str = "V8"
    mileage: int = 50000
    maintenance_history: List[str] = None
    known_issues: List[str] = None
    
    def __post_init__(self):
        if self.maintenance_history is None:
            self.maintenance_history = []
        if self.known_issues is None:
            self.known_issues = []

@dataclass
class OBDContext:
    """OBD data context for prompts."""
    current_dtcs: List[str] = None
    live_data: Dict[str, float] = None
    freeze_frame_data: Dict[str, Any] = None
    readiness_status: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.current_dtcs is None:
            self.current_dtcs = []
        if self.live_data is None:
            self.live_data = {}
        if self.freeze_frame_data is None:
            self.freeze_frame_data = {}
        if self.readiness_status is None:
            self.readiness_status = {}

@dataclass
class PromptTemplate:
    """Structured prompt template with metadata."""
    name: str
    prompt_type: PromptType
    ai_provider: AIProvider
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: List[Dict[str, str]]
    constraints: List[str]
    expected_output_format: str
    version: str = "1.0"
    confidence_threshold: float = 0.8
    max_tokens: int = 2000
    temperature: float = 0.3
    
class PromptOptimizer:
    """Advanced prompt optimization system with engineering best practices."""
    
    def __init__(self):
        """Initialize the prompt optimizer."""
        self.logger = logging.getLogger(__name__)
        self.templates = {}
        self.performance_metrics = {}
        self.feedback_data = []
        
        # Load W222-specific knowledge base
        self.w222_knowledge = self._load_w222_knowledge()
        
        # Initialize prompt templates
        self._initialize_templates()
        
        self.logger.info("🧠 AI Prompt Optimizer initialized with W222 knowledge base")
    
    def _load_w222_knowledge(self) -> Dict[str, Any]:
        """Load Mercedes W222-specific knowledge base."""
        return {
            "common_dtcs": {
                "P0300": {
                    "description": "Random/Multiple Cylinder Misfire Detected",
                    "common_causes": ["Ignition coils", "Spark plugs", "Fuel injectors", "Carbon buildup"],
                    "severity": "high",
                    "immediate_action": "Reduce engine load, check for rough idle"
                },
                "P0171": {
                    "description": "System Too Lean (Bank 1)",
                    "common_causes": ["Vacuum leak", "MAF sensor", "Fuel pump", "Oxygen sensor"],
                    "severity": "medium",
                    "immediate_action": "Check for vacuum leaks, monitor fuel trims"
                },
                "P0420": {
                    "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                    "common_causes": ["Catalytic converter", "Oxygen sensors", "Engine misfire"],
                    "severity": "medium",
                    "immediate_action": "Monitor emissions, schedule catalyst inspection"
                }
            },
            "engine_specs": {
                "M276": {
                    "displacement": "3.0L",
                    "type": "V6 Biturbo",
                    "power": "333-367 hp",
                    "normal_operating_temp": "80-95°C",
                    "max_rpm": 6500
                },
                "M278": {
                    "displacement": "4.7L",
                    "type": "V8 Biturbo",
                    "power": "449-469 hp",
                    "normal_operating_temp": "80-95°C",
                    "max_rpm": 6000
                }
            },
            "maintenance_intervals": {
                "oil_change": {"miles": 10000, "months": 12},
                "air_filter": {"miles": 20000, "months": 24},
                "spark_plugs": {"miles": 60000, "months": 72},
                "transmission_service": {"miles": 80000, "months": 96}
            },
            "normal_ranges": {
                "coolant_temp": {"min": 80, "max": 95, "unit": "°C"},
                "oil_pressure": {"min": 2.0, "max": 6.0, "unit": "bar"},
                "fuel_pressure": {"min": 3.5, "max": 4.5, "unit": "bar"},
                "intake_air_temp": {"min": -10, "max": 60, "unit": "°C"}
            }
        }
    
    def _initialize_templates(self):
        """Initialize optimized prompt templates."""
        
        # Diagnostic Analysis Template
        self.templates[PromptType.DIAGNOSTIC_ANALYSIS] = PromptTemplate(
            name="W222 Diagnostic Analysis",
            prompt_type=PromptType.DIAGNOSTIC_ANALYSIS,
            ai_provider=AIProvider.CLAUDE,
            system_prompt="""You are an expert Mercedes-Benz W222 diagnostic technician with 20+ years of experience. 
You have deep knowledge of W222 systems, common issues, and repair procedures.

CRITICAL CONSTRAINTS:
- Only provide advice for Mercedes-Benz W222 (S-Class 2013-2020)
- Always prioritize safety - if unsure, recommend professional inspection
- Base recommendations on actual OBD data and known W222 patterns
- Provide confidence levels for all diagnoses (0-100%)
- Include estimated repair costs when possible
- Reference Mercedes TSBs and service bulletins when relevant

OUTPUT FORMAT:
- Primary Diagnosis: [Most likely cause with confidence %]
- Secondary Possibilities: [Alternative causes with confidence %]
- Immediate Actions: [What to do right now]
- Repair Recommendations: [Specific steps and parts]
- Safety Assessment: [Can vehicle be driven safely?]
- Estimated Cost: [Repair cost range]""",
            
            user_prompt_template="""MERCEDES W222 DIAGNOSTIC REQUEST

VEHICLE INFORMATION:
- Model: {vehicle_model}
- Year: {vehicle_year}
- Engine: {engine_type}
- Mileage: {mileage} miles

CURRENT SYMPTOMS:
{symptoms}

OBD DATA:
- Diagnostic Trouble Codes: {dtcs}
- Live Data: {live_data}
- Freeze Frame: {freeze_frame}
- Readiness Status: {readiness_status}

MAINTENANCE HISTORY:
{maintenance_history}

Please provide a comprehensive diagnostic analysis following the specified format.""",
            
            few_shot_examples=[
                {
                    "input": "P0300 with rough idle, mileage 75000",
                    "output": """Primary Diagnosis: Ignition coil failure (85% confidence)
Secondary Possibilities: Carbon buildup on intake valves (60%), Fuel injector issues (45%)
Immediate Actions: Reduce engine load, avoid high RPM until repaired
Repair Recommendations: Replace ignition coils and spark plugs, perform intake cleaning
Safety Assessment: Can be driven carefully for short distances
Estimated Cost: $800-1200"""
                }
            ],
            
            constraints=[
                "Only diagnose W222-specific issues",
                "Always include confidence percentages",
                "Prioritize safety in all recommendations",
                "Provide actionable next steps"
            ],
            
            expected_output_format="Structured diagnostic report with confidence levels",
            temperature=0.2  # Low temperature for precise technical analysis
        )
        
        # Trip Analysis Template
        self.templates[PromptType.TRIP_ANALYSIS] = PromptTemplate(
            name="W222 Trip Analysis",
            prompt_type=PromptType.TRIP_ANALYSIS,
            ai_provider=AIProvider.CLAUDE,
            system_prompt="""You are an expert automotive data analyst specializing in Mercedes-Benz W222 performance optimization.
You analyze driving patterns, fuel efficiency, and vehicle performance to provide actionable insights.

ANALYSIS FOCUS:
- Driving efficiency and fuel economy optimization
- Engine performance patterns
- Maintenance recommendations based on driving style
- Performance comparisons to W222 benchmarks
- Environmental impact assessment

CONSTRAINTS:
- Base analysis on actual OBD data patterns
- Provide specific, actionable recommendations
- Include efficiency scores (0-100)
- Compare to W222 baseline performance
- Consider driving conditions and vehicle age""",
            
            user_prompt_template="""TRIP ANALYSIS REQUEST - MERCEDES W222

TRIP DATA:
- Duration: {trip_duration} minutes
- Distance: {trip_distance} miles
- Average Speed: {avg_speed} mph
- Max Speed: {max_speed} mph

ENGINE PERFORMANCE:
- Average RPM: {avg_rpm}
- Max RPM: {max_rpm}
- Average Load: {avg_load}%
- Fuel Consumption: {fuel_consumed} gallons

ENVIRONMENTAL CONDITIONS:
- Temperature: {ambient_temp}°C
- Driving Type: {driving_type}

VEHICLE CONTEXT:
- Model Year: {vehicle_year}
- Engine: {engine_type}
- Mileage: {total_mileage}

Analyze this trip and provide optimization recommendations.""",
            
            few_shot_examples=[
                {
                    "input": "City driving, 15 mph avg, high RPM variations",
                    "output": """Efficiency Score: 72/100
Key Insights: Frequent stop-and-go driving detected, engine operating in inefficient range
Recommendations: Use ECO mode, anticipate traffic patterns, consider hybrid driving techniques
Fuel Economy: 18.5 MPG (W222 city average: 16-20 MPG)"""
                }
            ],
            
            constraints=[
                "Provide efficiency scores",
                "Compare to W222 benchmarks",
                "Include actionable driving tips",
                "Consider vehicle age and condition"
            ],
            
            expected_output_format="Trip analysis report with scores and recommendations",
            temperature=0.4  # Moderate temperature for analytical insights
        )
        
        # Predictive Maintenance Template
        self.templates[PromptType.PREDICTIVE_MAINTENANCE] = PromptTemplate(
            name="W222 Predictive Maintenance",
            prompt_type=PromptType.PREDICTIVE_MAINTENANCE,
            ai_provider=AIProvider.CLAUDE,
            system_prompt="""You are a Mercedes-Benz W222 predictive maintenance specialist with access to extensive 
service data and failure patterns. You predict maintenance needs based on vehicle data trends.

PREDICTION CAPABILITIES:
- Component wear prediction based on usage patterns
- Optimal maintenance timing recommendations
- Cost-benefit analysis of preventive vs reactive maintenance
- Risk assessment for component failures
- Seasonal maintenance recommendations

CONSTRAINTS:
- Base predictions on actual data trends and W222 service patterns
- Provide confidence levels for all predictions
- Include time/mileage estimates for recommended services
- Consider cost implications and prioritize by urgency
- Reference Mercedes maintenance schedules""",
            
            user_prompt_template="""PREDICTIVE MAINTENANCE ANALYSIS - W222

VEHICLE STATUS:
- Current Mileage: {current_mileage}
- Last Service: {last_service_date} at {last_service_mileage} miles
- Engine Type: {engine_type}
- Driving Pattern: {driving_pattern}

TREND DATA:
- Oil Life Remaining: {oil_life}%
- Engine Performance Trend: {engine_trend}
- Transmission Performance: {transmission_trend}
- Brake Wear Indicators: {brake_wear}

RECENT ISSUES:
{recent_issues}

Predict upcoming maintenance needs and provide prioritized recommendations.""",
            
            few_shot_examples=[
                {
                    "input": "75000 miles, oil life 15%, transmission shifts slightly delayed",
                    "output": """Immediate (0-1000 miles): Oil change service (95% confidence)
Near-term (1000-5000 miles): Transmission service recommended (75% confidence)
Future (5000-10000 miles): Spark plug replacement due (60% confidence)
Priority: 1. Oil change ($150), 2. Transmission service ($400), 3. Spark plugs ($300)"""
                }
            ],
            
            constraints=[
                "Provide time/mileage estimates",
                "Include confidence levels",
                "Prioritize by urgency and cost",
                "Reference Mercedes service intervals"
            ],
            
            expected_output_format="Prioritized maintenance schedule with predictions",
            temperature=0.3  # Low-moderate temperature for precise predictions
        )
    
    def generate_prompt(self, 
                       prompt_type: PromptType, 
                       vehicle_context: VehicleContext,
                       obd_context: OBDContext,
                       additional_context: Dict[str, Any] = None) -> Tuple[str, str, Dict[str, Any]]:
        """Generate optimized prompt with context injection."""
        
        if prompt_type not in self.templates:
            raise ValueError(f"Prompt type {prompt_type} not supported")
        
        template = self.templates[prompt_type]
        
        # Prepare context variables
        context_vars = {
            "vehicle_model": vehicle_context.model,
            "vehicle_year": vehicle_context.year,
            "engine_type": vehicle_context.engine_type,
            "mileage": vehicle_context.mileage,
            "maintenance_history": "\\n".join(vehicle_context.maintenance_history) if vehicle_context.maintenance_history else "No recent maintenance recorded",
            "dtcs": ", ".join(obd_context.current_dtcs) if obd_context.current_dtcs else "No active codes",
            "live_data": json.dumps(obd_context.live_data, indent=2) if obd_context.live_data else "No live data available",
            "freeze_frame": json.dumps(obd_context.freeze_frame_data, indent=2) if obd_context.freeze_frame_data else "No freeze frame data",
            "readiness_status": json.dumps(obd_context.readiness_status, indent=2) if obd_context.readiness_status else "Readiness status unknown"
        }
        
        # Add additional context if provided
        if additional_context:
            context_vars.update(additional_context)
        
        # Inject W222-specific knowledge
        context_vars.update(self._inject_w222_knowledge(obd_context))
        
        # Generate the prompt
        user_prompt = template.user_prompt_template.format(**context_vars)
        
        # Prepare metadata
        metadata = {
            "template_version": template.version,
            "prompt_type": prompt_type.value,
            "ai_provider": template.ai_provider.value,
            "max_tokens": template.max_tokens,
            "temperature": template.temperature,
            "confidence_threshold": template.confidence_threshold,
            "timestamp": datetime.now().isoformat(),
            "prompt_hash": hashlib.md5(user_prompt.encode()).hexdigest()
        }
        
        self.logger.info(f"Generated {prompt_type.value} prompt with hash {metadata['prompt_hash']}")
        
        return template.system_prompt, user_prompt, metadata
    
    def _inject_w222_knowledge(self, obd_context: OBDContext) -> Dict[str, str]:
        """Inject relevant W222 knowledge based on OBD context."""
        knowledge_injection = {}
        
        # Add relevant DTC information
        if obd_context.current_dtcs:
            dtc_info = []
            for dtc in obd_context.current_dtcs:
                if dtc in self.w222_knowledge["common_dtcs"]:
                    info = self.w222_knowledge["common_dtcs"][dtc]
                    dtc_info.append(f"{dtc}: {info['description']} (Severity: {info['severity']})")
            
            if dtc_info:
                knowledge_injection["dtc_knowledge"] = "\\n".join(dtc_info)
        
        # Add normal range context
        if obd_context.live_data:
            range_info = []
            for param, value in obd_context.live_data.items():
                param_key = param.lower().replace("_", "_")
                if param_key in self.w222_knowledge["normal_ranges"]:
                    range_data = self.w222_knowledge["normal_ranges"][param_key]
                    range_info.append(f"{param}: {value} (Normal: {range_data['min']}-{range_data['max']} {range_data['unit']})")
            
            if range_info:
                knowledge_injection["parameter_ranges"] = "\\n".join(range_info)
        
        return knowledge_injection
    
    def record_feedback(self, prompt_hash: str, user_rating: int, effectiveness_score: float, comments: str = ""):
        """Record feedback for prompt optimization."""
        feedback = {
            "prompt_hash": prompt_hash,
            "user_rating": user_rating,  # 1-5 scale
            "effectiveness_score": effectiveness_score,  # 0-1 scale
            "comments": comments,
            "timestamp": datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback)
        self.logger.info(f"Recorded feedback for prompt {prompt_hash}: rating={user_rating}, effectiveness={effectiveness_score}")
    
    def optimize_template(self, prompt_type: PromptType) -> bool:
        """Optimize template based on feedback data."""
        if prompt_type not in self.templates:
            return False
        
        # Analyze feedback for this prompt type
        relevant_feedback = [f for f in self.feedback_data 
                           if f.get("prompt_type") == prompt_type.value]
        
        if len(relevant_feedback) < 10:  # Need minimum feedback samples
            self.logger.warning(f"Insufficient feedback data for {prompt_type.value} optimization")
            return False
        
        # Calculate average effectiveness
        avg_effectiveness = sum(f["effectiveness_score"] for f in relevant_feedback) / len(relevant_feedback)
        avg_rating = sum(f["user_rating"] for f in relevant_feedback) / len(relevant_feedback)
        
        self.logger.info(f"Template {prompt_type.value} performance: effectiveness={avg_effectiveness:.2f}, rating={avg_rating:.2f}")
        
        # If performance is below threshold, flag for manual review
        if avg_effectiveness < 0.7 or avg_rating < 3.5:
            self.logger.warning(f"Template {prompt_type.value} performance below threshold - manual review recommended")
            return False
        
        return True
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for all prompt templates."""
        metrics = {}
        
        for prompt_type in PromptType:
            relevant_feedback = [f for f in self.feedback_data 
                               if f.get("prompt_type") == prompt_type.value]
            
            if relevant_feedback:
                metrics[prompt_type.value] = {
                    "sample_count": len(relevant_feedback),
                    "avg_effectiveness": sum(f["effectiveness_score"] for f in relevant_feedback) / len(relevant_feedback),
                    "avg_rating": sum(f["user_rating"] for f in relevant_feedback) / len(relevant_feedback),
                    "last_updated": max(f["timestamp"] for f in relevant_feedback)
                }
            else:
                metrics[prompt_type.value] = {
                    "sample_count": 0,
                    "avg_effectiveness": 0,
                    "avg_rating": 0,
                    "last_updated": None
                }
        
        return metrics

# Example usage and testing
def test_prompt_optimizer():
    """Test the prompt optimizer with sample data."""
    optimizer = PromptOptimizer()
    
    # Create sample contexts
    vehicle_context = VehicleContext(
        model="W222",
        year=2018,
        engine_type="M276 V6 Biturbo",
        mileage=65000,
        maintenance_history=["Oil change at 60000 miles", "Brake service at 55000 miles"]
    )
    
    obd_context = OBDContext(
        current_dtcs=["P0300", "P0171"],
        live_data={
            "engine_rpm": 2150,
            "coolant_temp": 92,
            "engine_load": 45.5,
            "fuel_level": 75.0
        },
        readiness_status={"catalyst": True, "evap": False}
    )
    
    # Generate diagnostic prompt
    system_prompt, user_prompt, metadata = optimizer.generate_prompt(
        PromptType.DIAGNOSTIC_ANALYSIS,
        vehicle_context,
        obd_context,
        {"symptoms": "Rough idle, occasional stalling"}
    )
    
    print("=== GENERATED DIAGNOSTIC PROMPT ===")
    print("SYSTEM PROMPT:")
    print(system_prompt)
    print("\\nUSER PROMPT:")
    print(user_prompt)
    print("\\nMETADATA:")
    print(json.dumps(metadata, indent=2))
    
    return optimizer

if __name__ == "__main__":
    test_prompt_optimizer()
