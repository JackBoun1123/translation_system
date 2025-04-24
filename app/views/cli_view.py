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
                        self.console.print(f"[green]Translation: {result['translation']}[/green]")
                        last_translation = result["translation"]
                
                await asyncio.sleep(0.1)  # Small delay to prevent CPU hogging
                
        except Exception as e:
            self.console.print(f"[red]Error in streaming processing: {str(e)}[/red]")
        finally:
            self.streaming_active = False
    
    async def manage_context(self, *args):
        """Manage translation contexts"""
        if not args:
            self.console.print("[yellow]Context management requires an action.[/yellow]")
            self.console.print("[yellow]Usage: context [create|list|use|info|delete] [args][/yellow]")
            return False
        
        action = args[0].lower()
        
        if action == "create":
            return await self._create_context(*args[1:])
        elif action == "list":
            return await self._list_contexts()
        elif action == "use":
            return await self._use_context(*args[1:])
        elif action == "info":
            return await self._context_info(*args[1:])
        elif action == "delete":
            return await self._delete_context(*args[1:])
        else:
            self.console.print(f"[red]Unknown context action: {action}[/red]")
            self.console.print("[yellow]Available actions: create, list, use, info, delete[/yellow]")
            return False
    
    async def _create_context(self, *args):
        """Create a new translation context"""
        # Get context name
        if not args:
            name = self.prompt_session.prompt(
                HTML("<ansigreen>Enter context name: </ansigreen>")
            )
        else:
            name = args[0]
        
        # Get languages
        languages = []
        if len(args) > 1:
            languages = args[1].split(",")
        else:
            languages_input = self.prompt_session.prompt(
                HTML("<ansigreen>Enter language codes (comma-separated): </ansigreen>")
            )
            if languages_input:
                languages = [lang.strip() for lang in languages_input.split(",")]
        
        # Get domain (optional)
        domain = None
        if len(args) > 2:
            domain = args[2]
        else:
            domain_input = self.prompt_session.prompt(
                HTML("<ansigreen>Enter domain (optional): </ansigreen>")
            )
            if domain_input:
                domain = domain_input
        
        # Get description (optional)
        description = None
        if len(args) > 3:
            description = " ".join(args[3:])
        else:
            description_input = self.prompt_session.prompt(
                HTML("<ansigreen>Enter description (optional): </ansigreen>")
            )
            if description_input:
                description = description_input
        
        # Create the context
        try:
            context_id = await self.context_controller.create_context(
                name=name,
                languages=languages,
                domain=domain,
                description=description
            )
            
            self.console.print(f"[green]Context created with ID: {context_id}[/green]")
            
            # Ask if user wants to use this context
            response = self.prompt_session.prompt(
                HTML("<ansigreen>Use this context now? (y/n): </ansigreen>")
            )
            if response.lower() in ("y", "yes"):
                self.current_context_id = context_id
                self.console.print(f"[green]Now using context: {name}[/green]")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error creating context: {str(e)}[/red]")
            return False
    
    async def _list_contexts(self):
        """List all available contexts"""
        try:
            contexts = await self.context_controller.list_contexts()
            
            if not contexts:
                self.console.print("[yellow]No contexts found.[/yellow]")
                return True
            
            table = Table(title="Available Contexts")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Languages", style="yellow")
            table.add_column("Domain", style="magenta")
            
            for ctx in contexts:
                languages = ", ".join(ctx.get("languages", []))
                table.add_row(
                    str(ctx["id"]),
                    ctx["name"],
                    languages,
                    ctx.get("domain", "")
                )
            
            self.console.print(table)
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error listing contexts: {str(e)}[/red]")
            return False
    
    async def _use_context(self, *args):
        """Set current context by ID or name"""
        if not args:
            self.console.print("[red]No context ID provided.[/red]")
            self.console.print("[yellow]Usage: context use <context_id>[/yellow]")
            return False
        
        context_id = args[0]
        
        try:
            # Try to get context by ID first
            context = await self.context_controller.get_context(context_id)
            
            # If not found, try to find by name
            if not context:
                contexts = await self.context_controller.list_contexts()
                for ctx in contexts:
                    if ctx["name"].lower() == context_id.lower():
                        context = ctx
                        context_id = ctx["id"]
                        break
            
            if not context:
                self.console.print(f"[red]Context not found: {context_id}[/red]")
                return False
            
            self.current_context_id = context_id
            self.console.print(f"[green]Now using context: {context['name']}[/green]")
            
            # Update languages if available in context
            if context.get("languages") and len(context["languages"]) >= 2:
                # Set first language as source, second as target
                response = self.prompt_session.prompt(
                    HTML("<ansigreen>Also set languages from this context? (y/n): </ansigreen>")
                )
                if response.lower() in ("y", "yes"):
                    self.current_source_language = context["languages"][0]
                    self.current_target_language = context["languages"][1]
                    self.console.print(f"[green]Source language set to: {self.current_source_language}[/green]")
                    self.console.print(f"[green]Target language set to: {self.current_target_language}[/green]")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error setting context: {str(e)}[/red]")
            return False
    
    async def _context_info(self, *args):
        """Show detailed information about a context"""
        if not args:
            # If no ID provided, show current context
            if not self.current_context_id:
                self.console.print("[yellow]No active context.[/yellow]")
                return False
            context_id = self.current_context_id
        else:
            context_id = args[0]
        
        try:
            context = await self.context_controller.get_context(context_id)
            
            if not context:
                self.console.print(f"[red]Context not found: {context_id}[/red]")
                return False
            
            # Display context details
            self.console.print(f"[bold blue]Context Details: {context['name']}[/bold blue]")
            self.console.print(f"ID: [cyan]{context_id}[/cyan]")
            self.console.print(f"Languages: [yellow]{', '.join(context.get('languages', []))}[/yellow]")
            
            if context.get("domain"):
                self.console.print(f"Domain: [magenta]{context['domain']}[/magenta]")
            
            if context.get("description"):
                self.console.print(f"Description: [green]{context['description']}[/green]")
            
            # Show memory entries count
            memory_count = await self.context_controller.get_memory_count(context_id)
            self.console.print(f"Memory entries: [cyan]{memory_count}[/cyan]")
            
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error getting context info: {str(e)}[/red]")
            return False
    
    async def _delete_context(self, *args):
        """Delete a context by ID"""
        if not args:
            self.console.print("[red]No context ID provided.[/red]")
            self.console.print("[yellow]Usage: context delete <context_id>[/yellow]")
            return False
        
        context_id = args[0]
        
        try:
            # Get context info first for confirmation
            context = await self.context_controller.get_context(context_id)
            
            if not context:
                self.console.print(f"[red]Context not found: {context_id}[/red]")
                return False
            
            # Confirm deletion
            response = self.prompt_session.prompt(
                HTML(f"<ansired>Delete context '{context['name']}'? This cannot be undone (y/n): </ansired>")
            )
            
            if response.lower() not in ("y", "yes"):
                self.console.print("[yellow]Context deletion cancelled.[/yellow]")
                return True
            
            # Delete context
            success = await self.context_controller.delete_context(context_id)
            
            if success:
                self.console.print(f"[green]Context '{context['name']}' deleted.[/green]")
                
                # Reset current context if it was the one deleted
                if self.current_context_id == context_id:
                    self.current_context_id = None
                    self.console.print("[yellow]Current context has been reset.[/yellow]")
                
                return True
            else:
                self.console.print(f"[red]Failed to delete context.[/red]")
                return False
            
        except Exception as e:
            self.console.print(f"[red]Error deleting context: {str(e)}[/red]")
            return False
    
    async def set_language(self, *args):
        """Set source or target language"""
        if len(args) < 2:
            self.console.print("[red]Insufficient arguments.[/red]")
            self.console.print("[yellow]Usage: language source|target <language_code>[/yellow]")
            return False
        
        language_type = args[0].lower()
        language_code = args[1]
        
        if language_type not in ("source", "target"):
            self.console.print(f"[red]Invalid language type: {language_type}[/red]")
            self.console.print("[yellow]Use 'source' or 'target'[/yellow]")
            return False
        
        if language_type == "source":
            self.current_source_language = language_code
            self.console.print(f"[green]Source language set to: {language_code}[/green]")
        else:
            self.current_target_language = language_code
            self.console.print(f"[green]Target language set to: {language_code}[/green]")
        
        return True
    
    async def run(self):
        """Run the CLI interface main loop"""
        self.show_welcome()
        
        while True:
            try:
                # Get command from user
                user_input = self.prompt_session.prompt(
                    HTML("<ansiblue>>> </ansiblue>"),
                    completer=self.command_completer
                )
                
                if not user_input.strip():
                    continue
                
                # Parse command and arguments
                parts = user_input.split()
                command = parts[0].lower()
                args = parts[1:]
                
                # Execute command if it exists
                if command in self.commands:
                    command_func = self.commands[command]["func"]
                    
                    # Run the command function
                    if asyncio.iscoroutinefunction(command_func):
                        await command_func(*args)
                    else:
                        command_func(*args)
                else:
                    # If not a command, treat as text to translate
                    await self.translate_text(*parts)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled.[/yellow]")
                continue
            except EOFError:
                self.exit_app()
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
    
    @staticmethod
    def parse_arguments():
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(description="Translation System CLI")
        parser.add_argument("--config", type=str, help="Path to configuration file")
        parser.add_argument("--source", type=str, help="Source language code")
        parser.add_argument("--target", type=str, help="Target language code")
        parser.add_argument("--context", type=str, help="Context ID to use")
        parser.add_argument("--verbose", action="store_true", help="Verbose output")
        
        return parser.parse_args()

def main():
    """Main entry point for the CLI application"""
    # Parse arguments
    args = CLIView.parse_arguments()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Load configuration
    config_path = args.config or "config.json"
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        print("Using default configuration.")
        config = {
            "version": "1.0.0",
            "audio": {
                "sample_rate": 16000,
                "channels": 1
            },
            "models": {
                "asr": {"default": "default"},
                "translation": {"default": "default"},
                "tts": {"default": "default"}
            }
        }
    
    # Create and run CLI view
    cli_view = CLIView(config)
    
    # Set command line arguments
    if args.source:
        cli_view.current_source_language = args.source
    if args.target:
        cli_view.current_target_language = args.target
    if args.context:
        cli_view.current_context_id = args.context
    
    # Run the event loop
    asyncio.run(cli_view.run())

if __name__ == "__main__":
    main()