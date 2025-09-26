"""
Анализатор поездок с использованием внешних AI API.
"""
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional

from ..data.database_manager import DatabaseManager

class TripAnalyzer:
    """Управляет анализом данных поездки с помощью AI."""

    def __init__(self, db_manager: DatabaseManager, openai_api_key: Optional[str] = None, grok_api_key: Optional[str] = None):
        self.db_manager = db_manager
        self.openai_api_key = openai_api_key
        self.grok_api_key = grok_api_key
        self.gpt_url = "https://api.openai.com/v1/chat/completions"
        self.grok_url = "https://api.groq.com/openai/v1/chat/completions" # Пример URL, может отличаться

    async def analyze_and_save_trip(self, session_id: str):
        """Основной метод для анализа и сохранения результатов."""
        summary = self.db_manager.get_session_summary(session_id)
        if not summary:
            return

        if not self.openai_api_key or not self.grok_api_key:
            analysis_result = {
                "gpt_analysis": "Mock GPT analysis: Efficient driving style noted.",
                "grok_critique": "Mock Grok critique: Could improve on acceleration smoothness.",
                "final_report": "Mock final report: Overall a good trip with minor areas for improvement.",
                "error": "API keys not configured. Using mock data."
            }
        else:
            analysis_result = await self.analyze_trip(summary)
        
        self.db_manager.save_trip_analysis(session_id, analysis_result)

    async def analyze_trip(self, trip_data: Dict[str, Any]) -> Dict[str, str]:
        try:
            gpt_analysis = await self._get_gpt_analysis(trip_data)
            grok_critique = await self._get_grok_critique(trip_data, gpt_analysis)
            final_report = self._combine_reports(gpt_analysis, grok_critique)
            return {
                "gpt_analysis": gpt_analysis,
                "grok_critique": grok_critique,
                "final_report": final_report
            }
        except Exception as e:
            return {"error": f"Ошибка анализа поездки: {e}"}

    async def _get_gpt_analysis(self, trip_data: Dict[str, Any]) -> str:
        prompt = f"Analyze the following trip data for a Mercedes W222... Data: {json.dumps(trip_data, indent=2)}"
        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        data = {"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}]}
        async with aiohttp.ClientSession() as session:
            return await self._call_api(session, self.gpt_url, headers, data)

    async def _get_grok_critique(self, trip_data: Dict[str, Any], gpt_analysis: str) -> str:
        prompt = f"Critique this analysis: {gpt_analysis}. Data: {json.dumps(trip_data, indent=2)}"
        headers = {"Authorization": f"Bearer {self.grok_api_key}"}
        data = {"model": "llama3-70b-8192", "messages": [{"role": "user", "content": prompt}]}
        async with aiohttp.ClientSession() as session:
            return await self._call_api(session, self.grok_url, headers, data)

    async def _call_api(self, session: aiohttp.ClientSession, url: str, headers: Dict, data: Dict) -> str:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"API Error: {e}"

    def _combine_reports(self, gpt_report: str, grok_report: str) -> str:
        return f"**Общий отчет по поездке:**\n\n**Резюме:**\n{gpt_report}\n\n**Технический анализ и дополнения:**\n{grok_report}"

