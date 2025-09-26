"""
Enhanced Trip Analyzer with Modern Claude API Integration
Supports latest Claude models with advanced multimodal capabilities
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass

# Import Anthropic SDK
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logging.warning("Anthropic SDK not available. Install with: pip install anthropic")

from ..data.database_manager import DatabaseManager


@dataclass
class TripAnalysisResult:
    """Enhanced trip analysis result structure"""

    session_id: str
    analysis_timestamp: datetime

    # Core analysis
    claude_analysis: str
    driving_score: float  # 0-100
    efficiency_score: float  # 0-100
    safety_score: float  # 0-100

    # Detailed insights
    fuel_efficiency_analysis: Dict[str, Any]
    driving_behavior_analysis: Dict[str, Any]
    maintenance_recommendations: List[Dict[str, Any]]
    anomaly_insights: List[Dict[str, Any]]

    # Predictive elements
    predicted_issues: List[Dict[str, Any]]
    optimization_suggestions: List[str]

    # Metadata
    confidence_score: float
    analysis_version: str
    error_message: Optional[str] = None


class EnhancedTripAnalyzer:
    """Enhanced Trip Analyzer with Claude API Integration"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)

        # Initialize Anthropic client
        self.anthropic_client = None
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.logger.info("Anthropic Claude API initialized successfully")
        else:
            self.logger.warning("Anthropic API not available - using fallback analysis")

        # Analysis configuration
        self.claude_model = "claude-3-5-sonnet-20241022"  # Latest model
        self.max_tokens = 4000
        self.temperature = 0.3

    async def analyze_trip_comprehensive(
        self, session_id: str, vehicle_profile: Optional[Dict[str, Any]] = None
    ) -> TripAnalysisResult:
        """Perform comprehensive trip analysis using Claude API"""
        try:
            # Get session data
            session_summary = self.db_manager.get_session_summary(session_id)
            if not session_summary:
                raise ValueError(f"Session {session_id} not found")

            # Prepare analysis data
            analysis_data = self._prepare_analysis_data(session_summary, vehicle_profile)

            # Perform Claude analysis if available
            if self.anthropic_client:
                claude_analysis = await self._perform_claude_analysis(analysis_data)
            else:
                claude_analysis = self._fallback_analysis(analysis_data)

            # Calculate scores
            scores = self._calculate_performance_scores(analysis_data, claude_analysis)

            # Generate recommendations
            recommendations = self._generate_maintenance_recommendations(
                analysis_data, claude_analysis
            )

            # Create result
            result = TripAnalysisResult(
                session_id=session_id,
                analysis_timestamp=datetime.now(),
                claude_analysis=claude_analysis.get("main_analysis", ""),
                driving_score=scores["driving_score"],
                efficiency_score=scores["efficiency_score"],
                safety_score=scores["safety_score"],
                fuel_efficiency_analysis=claude_analysis.get("fuel_efficiency", {}),
                driving_behavior_analysis=claude_analysis.get("driving_behavior", {}),
                maintenance_recommendations=recommendations,
                anomaly_insights=claude_analysis.get("anomalies", []),
                predicted_issues=claude_analysis.get("predictions", []),
                optimization_suggestions=claude_analysis.get("optimizations", []),
                confidence_score=claude_analysis.get("confidence", 0.8),
                analysis_version="2.0.0",
            )

            # Save to database
            self._save_analysis_result(result)

            return result

        except Exception as e:
            self.logger.error(f"Trip analysis failed for session {session_id}: {str(e)}")
            return TripAnalysisResult(
                session_id=session_id,
                analysis_timestamp=datetime.now(),
                claude_analysis="",
                driving_score=0,
                efficiency_score=0,
                safety_score=0,
                fuel_efficiency_analysis={},
                driving_behavior_analysis={},
                maintenance_recommendations=[],
                anomaly_insights=[],
                predicted_issues=[],
                optimization_suggestions=[],
                confidence_score=0,
                analysis_version="2.0.0",
                error_message=str(e),
            )

    def _prepare_analysis_data(
        self, session_summary: Dict[str, Any], vehicle_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare comprehensive data for analysis"""
        session_info = session_summary.get("session_info", {})
        parameters = session_summary.get("parameters", {})
        anomalies = session_summary.get("anomalies", {})

        # Calculate derived metrics
        duration_hours = session_summary.get("duration_minutes", 0) / 60
        distance = session_info.get("trip_distance", 0)
        fuel_consumed = session_info.get("fuel_consumed", 0)

        # Engine performance metrics
        engine_metrics = {}
        if "ENGINE_RPM" in parameters:
            engine_metrics["avg_rpm"] = parameters["ENGINE_RPM"]["avg"]
            engine_metrics["max_rpm"] = parameters["ENGINE_RPM"]["max"]

        if "ENGINE_LOAD" in parameters:
            engine_metrics["avg_load"] = parameters["ENGINE_LOAD"]["avg"]
            engine_metrics["max_load"] = parameters["ENGINE_LOAD"]["max"]

        if "COOLANT_TEMP" in parameters:
            engine_metrics["avg_temp"] = parameters["COOLANT_TEMP"]["avg"]
            engine_metrics["max_temp"] = parameters["COOLANT_TEMP"]["max"]

        # Fuel efficiency
        fuel_efficiency = {}
        if distance > 0 and fuel_consumed > 0:
            fuel_efficiency["consumption_per_100km"] = (fuel_consumed / distance) * 100
            fuel_efficiency["efficiency_rating"] = self._rate_fuel_efficiency(
                fuel_efficiency["consumption_per_100km"]
            )

        # Speed analysis
        speed_analysis = {}
        if "SPEED" in parameters:
            speed_analysis["avg_speed"] = parameters["SPEED"]["avg"]
            speed_analysis["max_speed"] = parameters["SPEED"]["max"]
            speed_analysis["speed_variability"] = self._calculate_speed_variability(
                session_summary["session_info"]["session_id"]
            )

        return {
            "session_info": session_info,
            "duration_hours": duration_hours,
            "distance_km": distance,
            "fuel_consumed_liters": fuel_consumed,
            "engine_metrics": engine_metrics,
            "fuel_efficiency": fuel_efficiency,
            "speed_analysis": speed_analysis,
            "anomalies": anomalies,
            "vehicle_profile": vehicle_profile or {},
            "parameter_quality": {
                name: data.get("quality", 1.0) for name, data in parameters.items()
            },
        }

    async def _perform_claude_analysis(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform analysis using Claude API"""
        try:
            # Create comprehensive prompt
            prompt = self._create_analysis_prompt(analysis_data)

            # Call Claude API
            response = await asyncio.to_thread(
                self.anthropic_client.messages.create,
                model=self.claude_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            analysis_text = response.content[0].text
            return self._parse_claude_response(analysis_text)

        except Exception as e:
            self.logger.error(f"Claude API analysis failed: {str(e)}")
            return self._fallback_analysis(analysis_data)

    def _create_analysis_prompt(self, analysis_data: Dict[str, Any]) -> str:
        """Create comprehensive analysis prompt for Claude"""
        vehicle_info = analysis_data.get("vehicle_profile", {})
        vehicle_desc = (
            f"Mercedes-Benz W222 {vehicle_info.get('model', 'S-Class')}"
            if vehicle_info
            else "Mercedes-Benz W222 S-Class"
        )

        prompt = f"""
You are an expert automotive diagnostician and data analyst specializing in Mercedes-Benz vehicles, particularly the W222 S-Class platform. Analyze the following comprehensive trip data and provide detailed insights.

VEHICLE INFORMATION:
- Vehicle: {vehicle_desc}
- Engine Type: {vehicle_info.get('engine_type', 'Unknown')}
- Transmission: {vehicle_info.get('transmission_type', 'Unknown')}
- Mileage: {vehicle_info.get('mileage', 'Unknown')} km

TRIP DATA:
- Duration: {analysis_data.get('duration_hours', 0):.2f} hours
- Distance: {analysis_data.get('distance_km', 0):.1f} km
- Fuel Consumed: {analysis_data.get('fuel_consumed_liters', 0):.2f} liters

ENGINE METRICS:
{json.dumps(analysis_data.get('engine_metrics', {}), indent=2)}

FUEL EFFICIENCY:
{json.dumps(analysis_data.get('fuel_efficiency', {}), indent=2)}

SPEED ANALYSIS:
{json.dumps(analysis_data.get('speed_analysis', {}), indent=2)}

DETECTED ANOMALIES:
{json.dumps(analysis_data.get('anomalies', {}), indent=2)}

DATA QUALITY SCORES:
{json.dumps(analysis_data.get('parameter_quality', {}), indent=2)}

Please provide a comprehensive analysis in the following JSON format:

{{
    "main_analysis": "Detailed narrative analysis of the trip performance, driving behavior, and vehicle condition",
    "driving_score": <0-100 score based on driving efficiency, smoothness, and safety>,
    "efficiency_score": <0-100 score based on fuel consumption and engine efficiency>,
    "safety_score": <0-100 score based on speed patterns, engine stress, and anomalies>,
    "fuel_efficiency": {{
        "rating": "excellent|good|average|poor",
        "comparison_to_standard": "percentage above/below expected consumption",
        "factors_affecting": ["list of factors affecting fuel efficiency"]
    }},
    "driving_behavior": {{
        "style": "aggressive|moderate|conservative|eco-friendly",
        "acceleration_patterns": "analysis of acceleration behavior",
        "speed_consistency": "analysis of speed maintenance",
        "engine_stress_level": "low|moderate|high"
    }},
    "anomalies": [
        {{
            "type": "anomaly type",
            "severity": "low|medium|high|critical",
            "description": "detailed description",
            "potential_causes": ["list of potential causes"],
            "recommended_action": "immediate action needed"
        }}
    ],
    "predictions": [
        {{
            "component": "component name",
            "issue": "predicted issue",
            "timeframe": "estimated timeframe",
            "confidence": <0-1 confidence score>,
            "preventive_action": "recommended preventive action"
        }}
    ],
    "optimizations": [
        "List of specific suggestions to improve efficiency, performance, or longevity"
    ],
    "maintenance_priority": [
        {{
            "item": "maintenance item",
            "urgency": "immediate|soon|routine",
            "reason": "explanation of why this maintenance is needed"
        }}
    ],
    "confidence": <0-1 overall confidence in the analysis>
}}

Focus on:
1. Mercedes W222-specific characteristics and common issues
2. Real-world driving patterns and their implications
3. Predictive maintenance based on current data trends
4. Actionable recommendations for the vehicle owner
5. Integration of all available data points for comprehensive insights

Provide specific, actionable insights rather than generic advice.
"""
        return prompt

    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response"""
        try:
            # Try to extract JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create structured response from text
                return {
                    "main_analysis": response_text,
                    "driving_score": 75,
                    "efficiency_score": 70,
                    "safety_score": 80,
                    "fuel_efficiency": {"rating": "average"},
                    "driving_behavior": {"style": "moderate"},
                    "anomalies": [],
                    "predictions": [],
                    "optimizations": [],
                    "confidence": 0.7,
                }
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse Claude JSON response, using fallback")
            return {
                "main_analysis": response_text,
                "driving_score": 75,
                "efficiency_score": 70,
                "safety_score": 80,
                "fuel_efficiency": {"rating": "average"},
                "driving_behavior": {"style": "moderate"},
                "anomalies": [],
                "predictions": [],
                "optimizations": [],
                "confidence": 0.6,
            }

    def _fallback_analysis(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when Claude API is not available"""
        engine_metrics = analysis_data.get("engine_metrics", {})
        fuel_efficiency = analysis_data.get("fuel_efficiency", {})
        anomalies = analysis_data.get("anomalies", {})

        # Basic scoring
        driving_score = 75
        efficiency_score = 70
        safety_score = 80

        # Adjust scores based on available data
        if fuel_efficiency.get("consumption_per_100km"):
            consumption = fuel_efficiency["consumption_per_100km"]
            if consumption < 8:  # Excellent for W222
                efficiency_score = 90
            elif consumption < 10:  # Good
                efficiency_score = 80
            elif consumption < 12:  # Average
                efficiency_score = 70
            else:  # Poor
                efficiency_score = 50

        # Adjust for anomalies
        total_anomalies = sum(anomalies.values())
        if total_anomalies > 0:
            safety_score -= min(total_anomalies * 10, 30)
            driving_score -= min(total_anomalies * 5, 20)

        main_analysis = f"""
Fallback Analysis for Mercedes W222 Trip:

Trip Duration: {analysis_data.get('duration_hours', 0):.2f} hours
Distance Covered: {analysis_data.get('distance_km', 0):.1f} km
Fuel Consumption: {analysis_data.get('fuel_consumed_liters', 0):.2f} liters

Engine Performance:
- Average RPM: {engine_metrics.get('avg_rpm', 'N/A')}
- Average Load: {engine_metrics.get('avg_load', 'N/A')}%
- Temperature Range: {engine_metrics.get('avg_temp', 'N/A')}°C

Fuel Efficiency: {fuel_efficiency.get('consumption_per_100km', 'N/A')} L/100km

Anomalies Detected: {total_anomalies} issues requiring attention

This analysis was generated using fallback algorithms. For detailed AI-powered insights,
please configure the Claude API integration.
        """.strip()

        return {
            "main_analysis": main_analysis,
            "driving_score": driving_score,
            "efficiency_score": efficiency_score,
            "safety_score": safety_score,
            "fuel_efficiency": {
                "rating": fuel_efficiency.get("efficiency_rating", "average"),
                "consumption_per_100km": fuel_efficiency.get("consumption_per_100km", 0),
            },
            "driving_behavior": {"style": "moderate", "engine_stress_level": "moderate"},
            "anomalies": [],
            "predictions": [],
            "optimizations": [
                "Configure Claude API for detailed AI analysis",
                "Monitor fuel consumption patterns",
                "Regular maintenance schedule adherence",
            ],
            "confidence": 0.6,
        }

    def _calculate_performance_scores(
        self, analysis_data: Dict[str, Any], claude_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate performance scores"""
        # Use Claude scores if available, otherwise calculate
        return {
            "driving_score": claude_analysis.get("driving_score", 75.0),
            "efficiency_score": claude_analysis.get("efficiency_score", 70.0),
            "safety_score": claude_analysis.get("safety_score", 80.0),
        }

    def _generate_maintenance_recommendations(
        self, analysis_data: Dict[str, Any], claude_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate maintenance recommendations"""
        recommendations = claude_analysis.get("maintenance_priority", [])

        # Add default recommendations if none provided
        if not recommendations:
            recommendations = [
                {
                    "item": "Engine Oil Change",
                    "urgency": "routine",
                    "reason": "Regular maintenance schedule",
                },
                {
                    "item": "Air Filter Inspection",
                    "urgency": "routine",
                    "reason": "Maintain optimal engine performance",
                },
            ]

        return recommendations

    def _rate_fuel_efficiency(self, consumption_per_100km: float) -> str:
        """Rate fuel efficiency for W222 S-Class"""
        if consumption_per_100km < 8:
            return "excellent"
        elif consumption_per_100km < 10:
            return "good"
        elif consumption_per_100km < 12:
            return "average"
        else:
            return "poor"

    def _calculate_speed_variability(self, session_id: str) -> float:
        """Calculate speed variability from session data"""
        try:
            # Get speed data from database
            speed_data = self.db_manager.get_training_data(["SPEED"], session_id=session_id)
            if not speed_data.empty:
                return float(speed_data["value"].std())
            return 0.0
        except Exception:
            return 0.0

    def _save_analysis_result(self, result: TripAnalysisResult):
        """Save analysis result to database"""
        analysis_data = {
            "gpt_analysis": result.claude_analysis,  # Keep field name for compatibility
            "final_report": result.claude_analysis,
            "driving_score": result.driving_score,
            "efficiency_score": result.efficiency_score,
            "safety_score": result.safety_score,
            "maintenance_recommendations": json.dumps(result.maintenance_recommendations),
            "error": result.error_message,
        }

        self.db_manager.save_trip_analysis(result.session_id, analysis_data)

    def get_historical_analysis(self, vehicle_id: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get historical analysis for trend analysis"""
        sessions = self.db_manager.get_sessions(vehicle_id=vehicle_id, limit=50)

        historical_data = []
        for session in sessions:
            if session.get("end_time"):
                analysis = self.db_manager.get_session_data(session["session_id"])
                if analysis:
                    historical_data.append(
                        {
                            "session_id": session["session_id"],
                            "date": session["start_time"],
                            "driving_score": analysis.get("driving_score", 0),
                            "efficiency_score": analysis.get("efficiency_score", 0),
                            "safety_score": analysis.get("safety_score", 0),
                            "distance": session.get("trip_distance", 0),
                            "fuel_consumed": session.get("fuel_consumed", 0),
                        }
                    )

        return historical_data

    async def batch_analyze_sessions(self, session_ids: List[str]) -> List[TripAnalysisResult]:
        """Analyze multiple sessions in batch"""
        results = []

        for session_id in session_ids:
            try:
                result = await self.analyze_trip_comprehensive(session_id)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to analyze session {session_id}: {str(e)}")
                continue

        return results
