"""
Advanced state management for graceful shutdown and resume functionality.
"""

import os
import json
import signal
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import config
from src.core.logger import get_logger


class StateManager:
    """Manages processing state for graceful shutdown and resume."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # State files
        self.state_file = "automation_state.json"
        self.checkpoint_file = "processing_checkpoint.json"
        
        # Current state
        self.current_state = {
            'status': 'idle',
            'current_video': None,
            'current_step': None,
            'processed_videos': [],
            'total_videos': 0,
            'start_time': None,
            'last_checkpoint': None
        }
        
        # Shutdown handling
        self.shutdown_requested = False
        self.processing_complete = threading.Event()
        self.state_lock = threading.Lock()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Load existing state
        self._load_state()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Windows-specific
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, self._signal_handler)
                
        except Exception as e:
            self.logger.warning(f"Could not setup signal handlers: {e}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_names = {2: 'SIGINT (Ctrl+C)', 15: 'SIGTERM'}
        signal_name = signal_names.get(signum, f'Signal {signum}')
        
        self.logger.info(f"🛑 Received {signal_name} - initiating graceful shutdown...")
        
        with self.state_lock:
            self.shutdown_requested = True
            self.current_state['status'] = 'shutting_down'
            self._save_state()
        
        self.logger.info("⏳ Waiting for current video processing to complete...")
        self.logger.info("   Press Ctrl+C again to force quit (may cause data loss)")
    
    def start_processing(self, total_videos: int) -> None:
        """Start processing session."""
        with self.state_lock:
            self.current_state.update({
                'status': 'processing',
                'total_videos': total_videos,
                'start_time': datetime.now().isoformat(),
                'processed_videos': [],
                'current_video': None,
                'current_step': None
            })
            self.shutdown_requested = False
            self.processing_complete.clear()
            self._save_state()
        
        self.logger.info(f"🚀 Started processing session: {total_videos} videos")
    
    def start_video_processing(self, video_info: Dict[str, Any]) -> None:
        """Mark start of individual video processing."""
        with self.state_lock:
            self.current_state.update({
                'current_video': {
                    'id': video_info.get('id'),
                    'title': video_info.get('title', 'Unknown')[:50],
                    'channel': video_info.get('channel'),
                    'started_at': datetime.now().isoformat()
                },
                'current_step': 'starting',
                'last_checkpoint': datetime.now().isoformat()
            })
            self._save_state()
    
    def update_processing_step(self, step_name: str, details: str = None) -> None:
        """Update current processing step."""
        with self.state_lock:
            self.current_state['current_step'] = step_name
            self.current_state['last_checkpoint'] = datetime.now().isoformat()
            
            if details:
                if 'step_details' not in self.current_state:
                    self.current_state['step_details'] = {}
                self.current_state['step_details'][step_name] = details
            
            self._save_state()
    
    def complete_video_processing(self, video_id: str, success: bool, error: str = None) -> None:
        """Mark completion of video processing."""
        with self.state_lock:
            processed_info = {
                'video_id': video_id,
                'success': success,
                'completed_at': datetime.now().isoformat(),
                'error': error
            }
            
            self.current_state['processed_videos'].append(processed_info)
            self.current_state['current_video'] = None
            self.current_state['current_step'] = 'completed' if success else 'failed'
            self._save_state()
        
        status = "✅ completed" if success else "❌ failed"
        self.logger.info(f"Video {video_id} processing {status}")
    
    def complete_processing(self) -> None:
        """Mark end of processing session."""
        with self.state_lock:
            self.current_state.update({
                'status': 'completed',
                'current_video': None,
                'current_step': None,
                'end_time': datetime.now().isoformat()
            })
            self._save_state()
            self.processing_complete.set()
        
        successful = len([v for v in self.current_state['processed_videos'] if v['success']])
        total = len(self.current_state['processed_videos'])
        
        self.logger.info(f"🏁 Processing session completed: {successful}/{total} videos successful")
    
    def should_shutdown(self) -> bool:
        """Check if graceful shutdown was requested."""
        return self.shutdown_requested
    
    def wait_for_shutdown_complete(self, timeout: float = 300) -> bool:
        """Wait for processing to complete after shutdown request."""
        return self.processing_complete.wait(timeout)
    
    def get_resume_info(self) -> Optional[Dict[str, Any]]:
        """Get information needed to resume processing."""
        try:
            if not Path(self.state_file).exists():
                return None
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Check if there's a session that needs resuming
            if state.get('status') in ['processing', 'shutting_down']:
                processed_video_ids = [v['video_id'] for v in state.get('processed_videos', [])]
                
                return {
                    'can_resume': True,
                    'previous_session': {
                        'start_time': state.get('start_time'),
                        'total_videos': state.get('total_videos', 0),
                        'processed_count': len(processed_video_ids),
                        'processed_video_ids': processed_video_ids,
                        'last_video': state.get('current_video'),
                        'last_step': state.get('current_step')
                    }
                }
            else:
                return {'can_resume': False}
                
        except Exception as e:
            self.logger.error(f"Could not get resume info: {e}")
            return None
    
    def clear_state(self) -> None:
        """Clear processing state (use when starting fresh)."""
        with self.state_lock:
            self.current_state = {
                'status': 'idle',
                'current_video': None,
                'current_step': None,
                'processed_videos': [],
                'total_videos': 0,
                'start_time': None,
                'last_checkpoint': None
            }
            self._save_state()
        
        # Also remove checkpoint file
        try:
            if Path(self.checkpoint_file).exists():
                Path(self.checkpoint_file).unlink()
        except:
            pass
        
        self.logger.info("🧹 Processing state cleared")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        with self.state_lock:
            status = self.current_state.copy()
            
            # Add computed fields
            if status['start_time']:
                try:
                    start_time = datetime.fromisoformat(status['start_time'])
                    elapsed = (datetime.now() - start_time).total_seconds()
                    status['elapsed_time'] = elapsed
                    
                    # Calculate progress
                    if status['total_videos'] > 0:
                        progress = len(status['processed_videos']) / status['total_videos']
                        status['progress_percent'] = progress * 100
                        
                        # Estimate time remaining
                        if progress > 0:
                            estimated_total = elapsed / progress
                            remaining = estimated_total - elapsed
                            status['estimated_remaining'] = max(0, remaining)
                            
                except:
                    pass
            
            return status
    
    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r') as f:
                    saved_state = json.load(f)
                    
                # Merge with current state
                self.current_state.update(saved_state)
                
        except Exception as e:
            self.logger.debug(f"Could not load state: {e}")
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.current_state, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not save state: {e}")
    
    def create_checkpoint(self, checkpoint_data: Dict[str, Any]) -> None:
        """Create detailed checkpoint for complex resume scenarios."""
        try:
            checkpoint = {
                'timestamp': datetime.now().isoformat(),
                'state_snapshot': self.current_state.copy(),
                'checkpoint_data': checkpoint_data
            }
            
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not create checkpoint: {e}")
    
    def print_status_summary(self) -> None:
        """Print a nice status summary."""
        status = self.get_current_status()
        
        self.logger.info("📊 Processing Status Summary:")
        self.logger.info(f"   Status: {status['status']}")
        
        if status.get('current_video'):
            video = status['current_video']
            self.logger.info(f"   Current Video: {video['title']} ({video['channel']})")
            self.logger.info(f"   Current Step: {status.get('current_step', 'unknown')}")
        
        if status.get('progress_percent') is not None:
            progress = status['progress_percent']
            self.logger.info(f"   Progress: {progress:.1f}%")
            
        if status.get('estimated_remaining'):
            remaining_min = status['estimated_remaining'] / 60
            self.logger.info(f"   Estimated Time Remaining: {remaining_min:.1f} minutes")
        
        processed = len(status.get('processed_videos', []))
        total = status.get('total_videos', 0)
        self.logger.info(f"   Videos Processed: {processed}/{total}")