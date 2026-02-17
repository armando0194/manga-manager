from flask import Flask, jsonify, request, send_file, render_template
from pathlib import Path
import logging
import base64

from database import Database
from cover_manager import CoverManager
from file_renamer import FileRenamer
from config import Config

logger = logging.getLogger('manga-manager.web')

class WebUI:
    """Web interface for manual review and monitoring."""
    
    def __init__(self, config: Config, database: Database, 
                 cover_manager: CoverManager, file_renamer: FileRenamer):
        """
        Args:
            config: Configuration instance
            database: Database instance
            cover_manager: CoverManager instance
            file_renamer: FileRenamer instance
        """
        self.config = config
        self.db = database
        self.cover_mgr = cover_manager
        self.renamer = file_renamer
        
        # Create Flask app
        self.app = Flask(__name__, 
                         template_folder='web/templates',
                         static_folder='web/static')
        
        self._setup_routes()
        logger.info("Web UI initialized")
    
    def _setup_routes(self):
        """Set up Flask routes."""
        
        # UI Pages
        self.app.route('/')(self._index)
        self.app.route('/review')(self._review_page)
        
        # API Endpoints
        self.app.route('/api/files/needs-review', methods=['GET'])(self._api_files_needing_review)
        self.app.route('/api/files/<int:file_id>', methods=['GET'])(self._api_get_file)
        self.app.route('/api/files/<int:file_id>/update', methods=['POST'])(self._api_update_file)
        self.app.route('/api/covers/upload', methods=['POST'])(self._api_upload_cover)
        self.app.route('/api/covers/<series>/<int:volume>', methods=['GET'])(self._api_get_cover)
        self.app.route('/api/stats', methods=['GET'])(self._api_stats)
    
    # UI Pages
    
    def _index(self):
        """Main dashboard page."""
        return render_template('index.html')
    
    def _review_page(self):
        """Manual review page."""
        return render_template('review.html')
    
    # API Endpoints
    
    def _api_files_needing_review(self):
        """Get list of files needing manual review."""
        try:
            files = self.db.get_files_needing_review()
            
            result = []
            for file in files:
                result.append({
                    'id': file['id'],
                    'filename': file['filename'],
                    'series': file['series'],
                    'volume': file['volume'],
                    'chapter': file['chapter'],
                    'file_path': file['file_path'],
                    'processed_date': file['processed_date'],
                    'error_message': file['error_message']
                })
            
            return jsonify({'success': True, 'files': result})
            
        except Exception as e:
            logger.error(f"Error getting files needing review: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _api_get_file(self, file_id):
        """Get details about a specific file."""
        try:
            # Get file from database
            cursor = self.db.conn.cursor()
            cursor.execute('SELECT * FROM processed_files WHERE id = ?', (file_id,))
            file = cursor.fetchone()
            
            if not file:
                return jsonify({'success': False, 'error': 'File not found'}), 404
            
            # Check if cover exists
            cover_exists = False
            if file['series'] and file['volume']:
                cover_exists = self.cover_mgr.has_cover(file['series'], file['volume'])
            
            return jsonify({
                'success': True,
                'file': {
                    'id': file['id'],
                    'filename': file['filename'],
                    'series': file['series'],
                    'volume': file['volume'],
                    'chapter': file['chapter'],
                    'file_path': file['file_path'],
                    'cover_path': file['cover_path'],
                    'status': file['status'],
                    'error_message': file['error_message'],
                    'has_cover': cover_exists
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting file {file_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _api_update_file(self, file_id):
        """Update file metadata (series, volume, chapter)."""
        try:
            data = request.get_json()
            
            series = data.get('series')
            volume = data.get('volume')
            chapter = data.get('chapter')
            
            if not all([series, chapter is not None]):
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
            # Update database
            cursor = self.db.conn.cursor()
            cursor.execute('''
                UPDATE processed_files 
                SET series = ?, volume = ?, chapter = ?, status = 'completed'
                WHERE id = ?
            ''', (series, volume, chapter, file_id))
            self.db.conn.commit()
            
            logger.info(f"Updated file {file_id}: {series} Vol.{volume} Ch.{chapter}")
            
            return jsonify({'success': True, 'message': 'File updated successfully'})
            
        except Exception as e:
            logger.error(f"Error updating file {file_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _api_upload_cover(self):
        """Handle cover image upload."""
        try:
            series = request.form.get('series')
            volume = request.form.get('volume')
            
            if not series or not volume:
                return jsonify({'success': False, 'error': 'Missing series or volume'}), 400
            
            volume = int(volume)
            
            # Get uploaded file
            if 'cover' not in request.files:
                return jsonify({'success': False, 'error': 'No cover file provided'}), 400
            
            cover_file = request.files['cover']
            if cover_file.filename == '':
                return jsonify({'success': False, 'error': 'Empty filename'}), 400
            
            # Read cover data
            cover_data = cover_file.read()
            
            # Save cover
            success, cover_path, message = self.cover_mgr.save_uploaded_cover(
                series, volume, cover_data
            )
            
            if success:
                logger.info(f"Cover uploaded for {series} Vol.{volume}")
                return jsonify({
                    'success': True,
                    'message': message,
                    'cover_path': str(cover_path)
                })
            else:
                return jsonify({'success': False, 'error': message}), 500
                
        except Exception as e:
            logger.error(f"Error uploading cover: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _api_get_cover(self, series, volume):
        """Get cover image for a series/volume."""
        try:
            cover_path = self.cover_mgr.get_existing_cover(series, volume)
            
            if cover_path and cover_path.exists():
                return send_file(cover_path, mimetype='image/jpeg')
            else:
                return jsonify({'success': False, 'error': 'Cover not found'}), 404
                
        except Exception as e:
            logger.error(f"Error getting cover for {series} Vol.{volume}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _api_stats(self):
        """Get processing statistics."""
        try:
            cursor = self.db.conn.cursor()
            
            # Count by status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM processed_files 
                GROUP BY status
            ''')
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Total files
            cursor.execute('SELECT COUNT(*) as total FROM processed_files')
            total = cursor.fetchone()['total']
            
            # Recent files
            cursor.execute('''
                SELECT * FROM processed_files 
                ORDER BY processed_date DESC 
                LIMIT 10
            ''')
            recent = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'success': True,
                'stats': {
                    'total': total,
                    'by_status': status_counts,
                    'recent': recent
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def run(self, host='0.0.0.0', port=8080, debug=False):
        """Start the web server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            debug: Enable debug mode
        """
        logger.info(f"Starting web UI on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
