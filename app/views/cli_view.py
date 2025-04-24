"""
Command Line Interface view for the translation system.

This module provides a CLI interface for the translation system,
allowing users to interact with the system through terminal commands.
"""

import os
import sys
import argparse
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Union, Callable
import sounddevice as sd
import soundfile as sf
import numpy as np
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich import print as rprint
import tempfile
import threading
import queue

# Import controllers
from ..controllers.asr_controller import ASRController
from ..controllers.translation_controller import TranslationController
from ..controllers.tts_controller import TTSController
from ..controllers.context_controller import ContextController
from ..controllers.streaming_controller import StreamingController

# Import utils
from ..utils.audio_utils import load_audio, save_audio

# Configure logger
logger = logging.getLogger(__name__)

class CLIView:
    """Command Line Interface View for the translation system"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the CLI view.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.console = Console()
        self.prompt_session = PromptSession()
        
        # Initialize controllers
        self.asr_controller = ASRController(config)
        self.translation_controller = TranslationController(config)
        self.tts_controller = TTSController(config)
        self.context_controller = ContextController(config)
        self.streaming_controller = StreamingController(config)
        
        # Audio recording settings
        self.sample_rate = config.get("audio", {}).get("sample_rate", 16000)
        self.channels = config.get("audio", {}).get("channels", 1)
        
        # Current context
        self.current_context_id = None
        self.current_source_language = None
        self.current_target_language = None
        
        # Streaming session
        self.streaming_active = False
        self.streaming_queue = queue.Queue()
        self.streaming_session_id = None
        
        # Commands dictionary for help and auto-completion
        self.commands = {
            "help": {
                "func": self.show_help,
                "help": "Show available commands"
            },
            "exit": {
                "func": self.exit_app,
                "help": "Exit the application"
            },
            "clear": {
                "func": self.clear_screen,
                "help": "Clear the screen"
            },
            "config": {
                "func": self.show_config,
                "help": "Show current configuration"
            },
            "translate": {
                "func": self.translate_text,
                "help": "Translate text (usage: translate <text>)"
            },
            "transcribe": {
                "func": self.transcribe_audio,
                "help": "Transcribe audio file (usage: transcribe <file_path>)"
            },
            "record": {
                "func": self.record_and_transcribe,
                "help": "Record audio and transcribe (usage: record [duration_in_seconds])"
            },
            "speak": {
                "func": self.synthesize_speech,
                "help": "Convert text to speech (usage: speak <text>)"
            },
            "stream": {
                "func": self.toggle_streaming,
                "help": "Toggle streaming translation mode"
            },
            "context": {
                "func": self.manage_context,
                "help": "Manage translation contexts (usage: context [create|list|use|info|delete] [args])"
            },
            "language": {
                "func": self.set_language,
                "help": "Set source/target language (usage: language source|target <language_code>)"
            },
        }
        
        self.command_completer = WordCompleter(list(self.commands.keys()))
    
    def show_welcome(self):
        """Display welcome message and system information"""
        self.console.print(f"[bold blue]Translation System CLI v{self.config.get('version', '1.0.0')}[/bold blue]")
        self.console.print("[yellow]Type 'help' to see available commands.[/yellow]")
        self.console.print("=" * 60)
        
        # Show current configuration
        if self.current_source_language:
            self.console.print(f"Source language: [green]{self.current_source_language}[/green]")
        if self.current_target_language:
            self.console.print(f"Target language: [green]{self.current_target_language}[/green]")
        if self.current_context_id:
            context = asyncio.run(self.context_controller.get_context(self.current_context_id))
            if context:
                self.console.print(f"Active context: [green]{context['name']}[/green]")
        
        self.console.print("=" * 60)
    
    def show_help(self, *args):
        """Show help information about available commands"""
        table = Table(title="Available Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")
        
        for cmd, details in self.commands.items():
            table.add_row(cmd, details["help"])
        
        self.console.print(table)
        return True
    
    def exit_app(self, *args):
        """Exit the application"""
        self.console.print("[yellow]Exiting translation system...[/yellow]")
        # Clean up any resources
        if self.streaming_active:
            self.toggle_streaming()
        sys.exit(0)
    
    def clear_screen(self, *args):
        """Clear the terminal screen"""
        clear()
        self.show_welcome()
        return True
    
    def show_config(self, *args):
        """Show current configuration"""
        table = Table(title="Current Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        # Add basic settings
        table.add_row("Source Language", self.current_source_language or "Auto-detect")
        table.add_row("Target Language", self.current_target_language or "Not set")
        
        # Add context info if set
        if self.current_context_id:
            context = asyncio.run(self.context_controller.get_context(self.current_context_id))
            if context:
                table.add_row("Active Context", context["name"])
                table.add_row("Context Languages", ", ".join(context["languages"]))
                if context.get("domain"):
                    table.add_row("Context Domain", context["domain"])
        else:
            table.add_row("Active Context", "None")
        
        # Add model information
        for model_type in ["asr", "translation", "tts"]:
            model_info = self.config.get("models", {}).get(model_type, {}).get("default", "Default")
            table.add_row(f"{model_type.upper()} Model", str(model_info))
        
        self.console.print(table)
        return True
    
    async def translate_text(self, *args):
        """Translate text"""
        if not args:
            self.console.print("[red]Error: No text provided for translation.[/red]")
            self.console.print("[yellow]Usage: translate <text>[/yellow]")
            return False
        
        text = " ".join(args)
        
        if not self.current_target_language:
            self.console.print("[red]Error: Target language not set. Use 'language target <code>' command.[/red]")
            return False
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[bold green]{task.completed} of {task.total}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Translating...", total=100)
            
            # Simulate progress for responsiveness
            progress.update(task, completed=30)
            
            result = await self.translation_controller.translate_text(
                text=text,
                source_language=self.current_source_language,
                target_language=self.current_target_language,
                context_id=self.current_context_id
            )
            
            progress.update(task, completed=100)
        
        # Display result
        table = Table(title="Translation Result")
        table.add_column("Original", style="cyan")
        table.add_column("Translation", style="green")
        
        table.add_row(text, result["translated_text"])
        if result.get("detected_language"):
            table.caption = f"Detected language: {result['detected_language']}"
        
        self.console.print(table)
        return True
    
    async def transcribe_audio(self, *args):
        """Transcribe audio from file"""
        if not args:
            self.console.print("[red]Error: No audio file path provided.[/red]")
            self.console.print("[yellow]Usage: transcribe <file_path>[/yellow]")
            return False
        
        file_path = args[0]
        if not os.path.exists(file_path):
            self.console.print(f"[red]Error: File '{file_path}' not found.[/red]")
            return False
        
        language = self.current_source_language
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Transcribing audio...", total=100)
            
            # Load audio file
            progress.update(task, completed=10, description="Loading audio...")
            try:
                audio_data, sr = load_audio(file_path, sample_rate=self.sample_rate)
            except Exception as e:
                self.console.print(f"[red]Error loading audio file: {str(e)}[/red]")
                return False
            
            # Process transcription
            progress.update(task, completed=30, description="Processing speech...")
            
            try:
                with open(file_path, "rb") as f:
                    audio_bytes = f.read()
                
                result = await self.asr_controller.transcribe(
                    audio_data=audio_bytes,
                    language=language,
                    context_id=self.current_context_id
                )
                
                progress.update(task, completed=100)
            except Exception as e:
                self.console.print(f"[red]Error during transcription: {str(e)}[/red]")
                return False
        
        # Display result
        self.console.print("[bold]Transcription Result:[/bold]")
        self.console.print(result["text"])
        
        if result.get("detected_language"):
            self.console.print(f"[dim]Detected language: {result['detected_language']}[/dim]")
        
        # Ask if user wants to translate the result
        if self.current_target_language:
            response = self.prompt_session.prompt(
                HTML("<ansigreen>Translate this transcription? (y/n): </ansigreen>")
            )
            if response.lower() in ("y", "yes"):
                await self.translate_text(result["text"])
        
        return True
    
    async def record_and_transcribe(self, *args):
        """Record audio from microphone and transcribe"""
        try:
            duration = 5.0  # default duration
            if args and args[0].isdigit():
                duration = float(args[0])
            
            self.console.print(f"[yellow]Recording for {duration} seconds...[/yellow]")
            self.console.print("[bold red]Press Ctrl+C to stop recording early[/bold red]")
            
            # Record audio
            try:
                audio_data = sd.rec(
                    int(duration * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32'
                )
                sd.wait()
            except KeyboardInterrupt:
                sd.stop()
                self.console.print("[yellow]Recording stopped.[/yellow]")
            
            self.console.print("[green]Recording complete.[/green]")
            
            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_filename = tmp_file.name
                sf.write(temp_filename, audio_data, self.sample_rate)
            
            # Process with transcribe method
            await self.transcribe_audio(temp_filename)
            
            # Clean up temp file
            os.unlink(temp_filename)
            
        except Exception as e:
            self.console.print(f"[red]Error in recording: {str(e)}[/red]")
            return False
        
        return True
    
    async def synthesize_speech(self, *args):
        """Convert text to speech"""
        if not args:
            self.console.print("[red]Error: No text provided for speech synthesis.[/red]")
            self.console.print("[yellow]Usage: speak <text>[/yellow]")
            return False
        
        text = " ".join(args)
        
        # Use target language for TTS if set, else prompt for language
        language = self.current_target_language
        if not language:
            self.console.print("[yellow]No target language set.[/yellow]")
            language = self.prompt_session.prompt(
                HTML("<ansigreen>Enter language code for speech (e.g. en, fr, es): </ansigreen>")
            )
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Generating speech...", total=100)
            
            # Simulate progress for responsiveness
            progress.update(task, completed=30)
            
            try:
                audio_data = await self.tts_controller.synthesize(
                    text=text,
                    language=language
                )
                
                progress.update(task, completed=100)
            except Exception as e:
                self.console.print(f"[red]Error generating speech: {str(e)}[/red]")
                return False
        
        # Save to temporary file for playback
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            temp_filename = tmp_file.name
            with open(temp_filename, "wb") as f:
                f.write(audio_data)
        
        self.console.print("[green]Playing audio...[/green]")
        
        # Play the audio
        try:
            data, sr = sf.read(temp_filename)
            sd.play(data, sr)
            sd.wait()
        except Exception as e:
            self.console.print(f"[red]Error playing audio: {str(e)}[/red]")
        finally:
            # Clean up temp file
            os.unlink(temp_filename)
        
        return True
    
    async def toggle_streaming(self, *args):
        """Toggle streaming translation mode"""
        if not self.current_target_language:
            self.console.print("[red]Error: Target language not set. Use 'language target <code>' command.[/red]")
            return False
        
        if self.streaming_active:
            # Stop streaming
            self.streaming_active = False
            self.console.print("[yellow]Stopping streaming translation...[/yellow]")
            
            # Clean up streaming session
            if self.streaming_session_id:
                await self.streaming_controller.close_session(self.streaming_session_id)
                self.streaming_session_id = None
            
            return True
        else:
            # Start streaming
            self.console.print("[green]Starting streaming translation...[/green]")
            self.console.print("[dim]Speak clearly into your microphone. Processing will happen in real-time.[/dim]")
            self.console.print("[bold red]Press Ctrl+C or type 'stream' again to stop streaming.[/bold red]")
            
            try:
                # Create streaming session
                self.streaming_session_id = await self.streaming_controller.create_session(
                    source_language=self.current_source_language,
                    target_language=self.current_target_language,
                    context_id=self.current_context_id
                )
                
                self.streaming_active = True
                
                # Start audio recording in a separate thread
                threading.Thread(
                    target=self._stream_audio_worker,
                    daemon=True
                ).start()
                
                # Start processing in a separate thread
                threading.Thread(
                    target=asyncio.run,
                    args=(self._process_streaming(),),
                    daemon=True
                ).start()
                
                return True
                
            except Exception as e:
                self.console.print(f"[red]Error starting streaming: {str(e)}[/red]")
                self.streaming_active = False
                return False
    
    def _stream_audio_worker(self):
        """Worker thread for streaming audio from microphone"""
        chunk_duration = 1.0  # seconds
        chunk_size = int(self.sample_rate * chunk_duration)
        
        def audio_callback(indata, frames, time, status):
            """Callback for audio stream"""
            if status:
                print(f"Status: {status}")
            
            if self.streaming_active:
                # Convert to bytes and put in queue
                audio_chunk = indata.copy()
                self.streaming_queue.put(audio_chunk)
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=audio_callback,
                blocksize=chunk_size
            ):
                while self.streaming_active:
                    sd.sleep(100)  # sleep for 100ms
        except Exception as e:
            self.console.print(f"[red]Error in audio streaming: {str(e)}[/red]")
            self.streaming_active = False
    
    async def _process_streaming(self):
        """Process audio chunks from the streaming queue"""
        try:
            last_transcript = ""
            last_translation = ""
            
            while self.streaming_active:
                if not self.streaming_queue.empty():
                    # Get audio chunk from queue
                    audio_chunk = self.streaming_queue.get()
                    
                    # Convert numpy array to bytes
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_file:
                        sf.write(tmp_file.name, audio_chunk, self.sample_rate)
                        with open(tmp_file.name, "rb") as f:
                            audio_bytes = f.read()
                    
                    # Process chunk
                    result = await self.streaming_controller.process_chunk(
                        session_id=self.streaming_session_id,
                        audio_chunk=audio_bytes
                    )
                    
                    # Display results if they've changed
                    if result.get("transcript") and result["transcript"] != last_transcript:
                        self.console.print(f"[cyan]You: {result['transcript']}[/cyan]")
                        last_transcript = result["transcript"]
                    
                    if result.get("translation") and result["translation"] != last_translation:
                        self.console.print(f"[green]Translation: {result['translation']}[