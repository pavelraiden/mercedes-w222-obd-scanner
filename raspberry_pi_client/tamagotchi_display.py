"""
Tamagotchi-style display for Mercedes W222 OBD Scanner Raspberry Pi client.
Inspired by Flipper Zero dolphin, provides engaging visual feedback.
"""

import pygame
import math
import time
import random
from typing import Dict, List, Tuple
from enum import Enum
from dataclasses import dataclass
import threading
import json
import os

# Initialize Pygame
pygame.init()

class CarState(Enum):
    """Car health states that affect the tamagotchi."""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"

class TamagotchiMood(Enum):
    """Tamagotchi mood states."""
    HAPPY = "happy"
    CONTENT = "content"
    WORRIED = "worried"
    SICK = "sick"
    SLEEPING = "sleeping"

@dataclass
class OBDData:
    """OBD data structure for tamagotchi."""
    engine_rpm: float = 0
    speed: float = 0
    coolant_temp: float = 0
    engine_load: float = 0
    fuel_level: float = 100
    errors: List[str] = None
    connected: bool = False
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class MercedesTamagotchi:
    """Mercedes-themed tamagotchi character for OBD scanner."""
    
    def __init__(self, screen_width: int = 320, screen_height: int = 240):
        """Initialize the tamagotchi display."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption("Mercedes OBD Tamagotchi")
        
        # Colors (Mercedes theme)
        self.colors = {
            'background': (15, 15, 25),      # Dark blue
            'mercedes_silver': (192, 192, 192),
            'mercedes_blue': (0, 51, 102),
            'white': (255, 255, 255),
            'green': (0, 255, 0),
            'yellow': (255, 255, 0),
            'red': (255, 0, 0),
            'orange': (255, 165, 0),
            'text': (220, 220, 220)
        }
        
        # Character state
        self.mood = TamagotchiMood.CONTENT
        self.car_state = CarState.OFFLINE
        self.obd_data = OBDData()
        
        # Animation variables
        self.animation_frame = 0
        self.animation_speed = 0.1
        self.blink_timer = 0
        self.bounce_offset = 0
        self.last_update = time.time()
        
        # Character position
        self.char_x = screen_width // 2
        self.char_y = screen_height // 2 - 20
        
        # Fonts
        try:
            self.font_large = pygame.font.Font(None, 24)
            self.font_small = pygame.font.Font(None, 16)
        except:
            self.font_large = pygame.font.SysFont('arial', 20)
            self.font_small = pygame.font.SysFont('arial', 14)
        
        # Stats
        self.happiness = 100
        self.health = 100
        self.energy = 100
        
        # Messages
        self.current_message = "Hello! I'm your Mercedes assistant!"
        self.message_timer = 0
        
        # Running state
        self.running = True
        self.clock = pygame.time.Clock()
        
        print("🐬 Mercedes Tamagotchi initialized!")
    
    def update_obd_data(self, obd_data: OBDData):
        """Update OBD data and adjust tamagotchi state."""
        self.obd_data = obd_data
        self._analyze_car_health()
        self._update_mood()
        self._update_stats()
    
    def _analyze_car_health(self):
        """Analyze OBD data to determine car health state."""
        if not self.obd_data.connected:
            self.car_state = CarState.OFFLINE
            return
        
        # Check for critical issues
        if self.obd_data.errors:
            self.car_state = CarState.CRITICAL
            return
        
        # Check temperature
        if self.obd_data.coolant_temp > 100:  # Over 100°C
            self.car_state = CarState.WARNING
            return
        
        # Check fuel level
        if self.obd_data.fuel_level < 10:
            self.car_state = CarState.WARNING
            return
        
        # Check engine load
        if self.obd_data.engine_load > 90:
            self.car_state = CarState.WARNING
            return
        
        # All good
        if self.obd_data.coolant_temp < 90 and self.obd_data.fuel_level > 25:
            self.car_state = CarState.EXCELLENT
        else:
            self.car_state = CarState.GOOD
    
    def _update_mood(self):
        """Update tamagotchi mood based on car state."""
        if self.car_state == CarState.OFFLINE:
            self.mood = TamagotchiMood.SLEEPING
        elif self.car_state == CarState.CRITICAL:
            self.mood = TamagotchiMood.SICK
        elif self.car_state == CarState.WARNING:
            self.mood = TamagotchiMood.WORRIED
        elif self.car_state == CarState.EXCELLENT:
            self.mood = TamagotchiMood.HAPPY
        else:
            self.mood = TamagotchiMood.CONTENT
    
    def _update_stats(self):
        """Update tamagotchi stats based on car condition."""
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Health based on car state
        if self.car_state == CarState.CRITICAL:
            self.health = max(0, self.health - 20 * dt)
        elif self.car_state == CarState.WARNING:
            self.health = max(0, self.health - 5 * dt)
        elif self.car_state == CarState.EXCELLENT:
            self.health = min(100, self.health + 2 * dt)
        
        # Happiness based on driving
        if self.obd_data.connected and self.obd_data.speed > 0:
            self.happiness = min(100, self.happiness + 1 * dt)
        else:
            self.happiness = max(0, self.happiness - 0.5 * dt)
        
        # Energy based on engine state
        if self.obd_data.engine_rpm > 0:
            self.energy = max(0, self.energy - 0.3 * dt)
        else:
            self.energy = min(100, self.energy + 2 * dt)
    
    def _draw_character(self):
        """Draw the tamagotchi character."""
        # Update animation
        self.animation_frame += self.animation_speed
        self.blink_timer += 0.02
        
        # Bounce effect when happy
        if self.mood == TamagotchiMood.HAPPY:
            self.bounce_offset = math.sin(self.animation_frame * 3) * 3
        else:
            self.bounce_offset = 0
        
        char_y = self.char_y + self.bounce_offset
        
        # Draw body (Mercedes star inspired)
        body_color = self.colors['mercedes_silver']
        if self.mood == TamagotchiMood.SICK:
            body_color = self.colors['red']
        elif self.mood == TamagotchiMood.WORRIED:
            body_color = self.colors['orange']
        elif self.mood == TamagotchiMood.HAPPY:
            body_color = self.colors['green']
        
        # Main body (circle)
        pygame.draw.circle(self.screen, body_color, (self.char_x, int(char_y)), 30)
        pygame.draw.circle(self.screen, self.colors['white'], (self.char_x, int(char_y)), 30, 2)
        
        # Mercedes star
        star_points = []
        for i in range(3):
            angle = i * 120 + self.animation_frame * 10
            x = self.char_x + math.cos(math.radians(angle)) * 15
            y = char_y + math.sin(math.radians(angle)) * 15
            star_points.append((x, y))
        
        if len(star_points) >= 3:
            pygame.draw.polygon(self.screen, self.colors['mercedes_blue'], star_points)
        
        # Eyes
        eye_y = char_y - 10
        left_eye_x = self.char_x - 10
        right_eye_x = self.char_x + 10
        
        # Blinking
        if self.blink_timer % 3 < 0.2:  # Blink every 3 seconds
            # Closed eyes
            pygame.draw.line(self.screen, self.colors['white'], 
                           (left_eye_x - 3, eye_y), (left_eye_x + 3, eye_y), 2)
            pygame.draw.line(self.screen, self.colors['white'], 
                           (right_eye_x - 3, eye_y), (right_eye_x + 3, eye_y), 2)
        else:
            # Open eyes
            if self.mood == TamagotchiMood.HAPPY:
                # Happy eyes (^_^)
                pygame.draw.arc(self.screen, self.colors['white'], 
                              (left_eye_x - 3, eye_y - 3, 6, 6), 0, math.pi, 2)
                pygame.draw.arc(self.screen, self.colors['white'], 
                              (right_eye_x - 3, eye_y - 3, 6, 6), 0, math.pi, 2)
            elif self.mood == TamagotchiMood.WORRIED:
                # Worried eyes
                pygame.draw.circle(self.screen, self.colors['white'], (left_eye_x, eye_y), 3)
                pygame.draw.circle(self.screen, self.colors['white'], (right_eye_x, eye_y), 3)
                pygame.draw.circle(self.screen, self.colors['background'], (left_eye_x, eye_y - 1), 1)
                pygame.draw.circle(self.screen, self.colors['background'], (right_eye_x, eye_y - 1), 1)
            elif self.mood == TamagotchiMood.SICK:
                # X eyes
                pygame.draw.line(self.screen, self.colors['red'], 
                               (left_eye_x - 3, eye_y - 3), (left_eye_x + 3, eye_y + 3), 2)
                pygame.draw.line(self.screen, self.colors['red'], 
                               (left_eye_x + 3, eye_y - 3), (left_eye_x - 3, eye_y + 3), 2)
                pygame.draw.line(self.screen, self.colors['red'], 
                               (right_eye_x - 3, eye_y - 3), (right_eye_x + 3, eye_y + 3), 2)
                pygame.draw.line(self.screen, self.colors['red'], 
                               (right_eye_x + 3, eye_y - 3), (right_eye_x - 3, eye_y + 3), 2)
            else:
                # Normal eyes
                pygame.draw.circle(self.screen, self.colors['white'], (left_eye_x, eye_y), 3)
                pygame.draw.circle(self.screen, self.colors['white'], (right_eye_x, eye_y), 3)
                pygame.draw.circle(self.screen, self.colors['background'], (left_eye_x, eye_y), 1)
                pygame.draw.circle(self.screen, self.colors['background'], (right_eye_x, eye_y), 1)
        
        # Mouth
        mouth_y = char_y + 10
        if self.mood == TamagotchiMood.HAPPY:
            # Smile
            pygame.draw.arc(self.screen, self.colors['white'], 
                          (self.char_x - 8, mouth_y - 4, 16, 8), 0, math.pi, 2)
        elif self.mood == TamagotchiMood.WORRIED or self.mood == TamagotchiMood.SICK:
            # Frown
            pygame.draw.arc(self.screen, self.colors['white'], 
                          (self.char_x - 8, mouth_y, 16, 8), math.pi, 2 * math.pi, 2)
        else:
            # Neutral
            pygame.draw.line(self.screen, self.colors['white'], 
                           (self.char_x - 5, mouth_y), (self.char_x + 5, mouth_y), 2)
    
    def _draw_stats(self):
        """Draw health, happiness, and energy bars."""
        bar_width = 60
        bar_height = 8
        bar_x = 10
        
        # Health bar
        health_y = 10
        pygame.draw.rect(self.screen, self.colors['red'], 
                        (bar_x, health_y, bar_width, bar_height))
        pygame.draw.rect(self.screen, self.colors['green'], 
                        (bar_x, health_y, int(bar_width * self.health / 100), bar_height))
        health_text = self.font_small.render(f"Health: {int(self.health)}%", True, self.colors['text'])
        self.screen.blit(health_text, (bar_x + bar_width + 5, health_y))
        
        # Happiness bar
        happiness_y = 25
        pygame.draw.rect(self.screen, self.colors['red'], 
                        (bar_x, happiness_y, bar_width, bar_height))
        pygame.draw.rect(self.screen, self.colors['yellow'], 
                        (bar_x, happiness_y, int(bar_width * self.happiness / 100), bar_height))
        happiness_text = self.font_small.render(f"Happy: {int(self.happiness)}%", True, self.colors['text'])
        self.screen.blit(happiness_text, (bar_x + bar_width + 5, happiness_y))
        
        # Energy bar
        energy_y = 40
        pygame.draw.rect(self.screen, self.colors['red'], 
                        (bar_x, energy_y, bar_width, bar_height))
        pygame.draw.rect(self.screen, self.colors['mercedes_blue'], 
                        (bar_x, energy_y, int(bar_width * self.energy / 100), bar_height))
        energy_text = self.font_small.render(f"Energy: {int(self.energy)}%", True, self.colors['text'])
        self.screen.blit(energy_text, (bar_x + bar_width + 5, energy_y))
    
    def _draw_obd_info(self):
        """Draw OBD information."""
        info_y = self.screen_height - 80
        
        if self.obd_data.connected:
            # Speed
            speed_text = self.font_small.render(f"Speed: {self.obd_data.speed:.0f} km/h", 
                                              True, self.colors['text'])
            self.screen.blit(speed_text, (10, info_y))
            
            # RPM
            rpm_text = self.font_small.render(f"RPM: {self.obd_data.engine_rpm:.0f}", 
                                            True, self.colors['text'])
            self.screen.blit(rpm_text, (10, info_y + 15))
            
            # Temperature
            temp_color = self.colors['text']
            if self.obd_data.coolant_temp > 100:
                temp_color = self.colors['red']
            elif self.obd_data.coolant_temp > 90:
                temp_color = self.colors['orange']
            
            temp_text = self.font_small.render(f"Temp: {self.obd_data.coolant_temp:.0f}°C", 
                                             True, temp_color)
            self.screen.blit(temp_text, (10, info_y + 30))
            
            # Fuel
            fuel_color = self.colors['text']
            if self.obd_data.fuel_level < 10:
                fuel_color = self.colors['red']
            elif self.obd_data.fuel_level < 25:
                fuel_color = self.colors['orange']
            
            fuel_text = self.font_small.render(f"Fuel: {self.obd_data.fuel_level:.0f}%", 
                                             True, fuel_color)
            self.screen.blit(fuel_text, (10, info_y + 45))
        else:
            offline_text = self.font_small.render("OBD Offline", True, self.colors['red'])
            self.screen.blit(offline_text, (10, info_y))
    
    def _draw_message(self):
        """Draw current message."""
        if self.current_message and self.message_timer > 0:
            message_y = self.screen_height - 30
            message_text = self.font_small.render(self.current_message, True, self.colors['white'])
            
            # Center the message
            text_rect = message_text.get_rect()
            text_x = (self.screen_width - text_rect.width) // 2
            
            # Draw background
            pygame.draw.rect(self.screen, self.colors['mercedes_blue'], 
                           (text_x - 5, message_y - 2, text_rect.width + 10, text_rect.height + 4))
            
            self.screen.blit(message_text, (text_x, message_y))
            self.message_timer -= 1
    
    def show_message(self, message: str, duration: int = 180):  # 3 seconds at 60 FPS
        """Show a message for a specified duration."""
        self.current_message = message
        self.message_timer = duration
    
    def _generate_contextual_message(self):
        """Generate contextual messages based on car state."""
        messages = {
            CarState.EXCELLENT: [
                "Your Mercedes is purring perfectly! 😊",
                "All systems optimal! Ready for adventure!",
                "Engine running smoothly! I'm so happy!",
                "Perfect driving conditions detected!"
            ],
            CarState.GOOD: [
                "Everything looks good! 👍",
                "Your Mercedes is running well!",
                "All systems normal!",
                "Smooth sailing ahead!"
            ],
            CarState.WARNING: [
                "Something needs attention... 😟",
                "Warning detected! Check diagnostics!",
                "I'm a bit worried about something...",
                "Please check the warning indicators!"
            ],
            CarState.CRITICAL: [
                "URGENT! Critical issue detected! 🚨",
                "Please stop safely and check engine!",
                "Critical error! I need help!",
                "Emergency! Pull over safely!"
            ],
            CarState.OFFLINE: [
                "Zzz... OBD connection lost...",
                "Sleeping until connection returns...",
                "Waiting for OBD data...",
                "Connect me to your Mercedes!"
            ]
        }
        
        if random.random() < 0.01:  # 1% chance per frame
            message_list = messages.get(self.car_state, ["Hello!"])
            self.show_message(random.choice(message_list))
    
    def update(self):
        """Update the tamagotchi display."""
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    self.show_message("Hello! I'm your Mercedes assistant! 🚗")
        
        # Generate contextual messages
        self._generate_contextual_message()
        
        # Clear screen
        self.screen.fill(self.colors['background'])
        
        # Draw components
        self._draw_character()
        self._draw_stats()
        self._draw_obd_info()
        self._draw_message()
        
        # Update display
        pygame.display.flip()
        self.clock.tick(60)  # 60 FPS
    
    def run(self):
        """Main display loop."""
        print("🐬 Mercedes Tamagotchi started! Press SPACE to interact, ESC to quit.")
        
        while self.running:
            self.update()
        
        pygame.quit()
        print("🐬 Mercedes Tamagotchi stopped!")

# Demo/Testing function
def demo_tamagotchi():
    """Demo the tamagotchi with simulated OBD data."""
    tamagotchi = MercedesTamagotchi()
    
    # Simulate different car states
    demo_states = [
        # Normal driving
        OBDData(engine_rpm=2000, speed=60, coolant_temp=85, fuel_level=75, connected=True),
        # Highway driving
        OBDData(engine_rpm=2500, speed=120, coolant_temp=88, fuel_level=70, connected=True),
        # City traffic
        OBDData(engine_rpm=800, speed=15, coolant_temp=82, fuel_level=65, connected=True),
        # Low fuel warning
        OBDData(engine_rpm=1500, speed=50, coolant_temp=86, fuel_level=8, connected=True),
        # Overheating
        OBDData(engine_rpm=3000, speed=80, coolant_temp=105, fuel_level=60, connected=True),
        # Engine error
        OBDData(engine_rpm=0, speed=0, coolant_temp=95, fuel_level=55, 
               errors=["P0301 - Cylinder 1 Misfire"], connected=True),
        # Offline
        OBDData(connected=False)
    ]
    
    state_index = 0
    state_timer = 0
    
    while tamagotchi.running:
        # Change state every 5 seconds
        if state_timer % 300 == 0:  # 5 seconds at 60 FPS
            tamagotchi.update_obd_data(demo_states[state_index])
            state_index = (state_index + 1) % len(demo_states)
        
        state_timer += 1
        tamagotchi.update()

if __name__ == "__main__":
    # Run demo
    demo_tamagotchi()
