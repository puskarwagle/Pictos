"""
Maintenance script for cleaning up orphaned and soft-deleted image files and database records.

This script prevents the local 'downloaded_images' folder from growing indefinitely by 
removing files that are no longer referenced by any active scripts or have been 
explicitly deleted by the user.

Key Concepts:
- 'orphaned': Images linked to text segments that were removed during a script edit.
- 'deleted': Images explicitly removed by the user via the UI (soft-delete).
- 'user_touched': A flag that prevents automatic deletion of images the user has 
  interacted with (e.g., pinned or specifically selected).

Logic:
1. Queries the 'images' table for records with status 'orphaned' or 'deleted' that 
   exceed the Time-To-Live (TTL) period.
2. For each candidate, checks if the physical file is referenced by any OTHER 
   active database record (to avoid deleting shared assets).
3. If safe, deletes the physical file from disk.
4. Removes the record from the 'images' table.
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from app.db.session import get_db
from app.db.repository import can_delete_file

def gc(dry_run=True, ttl_days=30):
    """
    Performs the garbage collection routine.
    
    Args:
        dry_run (bool): If True, only reports what would be deleted without 
                         modifying the disk or DB.
        ttl_days (int): Minimum age of a record (since creation) before it's 
                         eligible for cleanup.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=ttl_days)
    
    report = {
        "db_records_removed": 0,
        "physical_files_unlinked": [],
        "orphaned_removed": 0,
        "trash_removed": 0,
        "total_size_freed": 0
    }

    print(f"Starting Garbage Collection (Dry Run: {dry_run}, TTL: {ttl_days} days)")
    print(f"Cutoff date: {cutoff_date}")

    # 1. Identify candidates for deletion based on status and age
    # - Orphaned: No longer in any script, hasn't been touched by user, and older than TTL.
    # - Deleted: Explicitly soft-deleted by user and older than TTL.
    cursor.execute("""
        SELECT id, file_path, status FROM images
        WHERE (status = 'orphaned' AND created_at < ? AND user_touched = 0)
           OR (status = 'deleted' AND created_at < ?)
    """, (cutoff_date, cutoff_date))
    
    candidates = cursor.fetchall()
    
    for candidate in candidates:
        img_id, path_str, status = candidate
        path = Path(path_str)
        
        size = 0
        if path.exists():
            size = path.stat().st_size
            
        # Check if file can be safely deleted (no other active or pinned records reference it)
        # This is crucial because multiple anchors or scripts might point to the same physical file.
        safe_to_delete = can_delete_file(path_str, conn)

        if not dry_run:
            try:
                if safe_to_delete and path.exists():
                    path.unlink()
                    report["physical_files_unlinked"].append(path_str)
                
                # Always remove the DB record for the candidate, even if the file is shared
                cursor.execute("DELETE FROM images WHERE id = ?", (img_id,))
                report["db_records_removed"] += 1
            except Exception as e:
                print(f"Error deleting {path_str}: {e}")
                continue
        else:
            report["db_records_removed"] += 1
            # In dry run, we assume it would be deleted if safe and present
            if safe_to_delete:
                report["physical_files_unlinked"].append(f"[DRY RUN] {path_str}")

        if status == 'orphaned': 
            report["orphaned_removed"] += 1
        else: 
            report["trash_removed"] += 1
            
        if safe_to_delete:
            report["total_size_freed"] += size

    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print("\n--- GC Summary ---")
    print(f"DB Records removed: {report['db_records_removed']}")
    print(f"Physical files unlinked: {len(report['physical_files_unlinked'])}")
    print(f"  - From Orphaned: {report['orphaned_removed']}")
    print(f"  - From Trash: {report['trash_removed']}")
    print(f"Total size freed: {report['total_size_freed'] / 1024 / 1024:.2f} MB")
    
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Garbage Collect orphaned/deleted images")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually delete files and DB records")
    parser.add_argument("--ttl", type=int, default=30, help="TTL in days (default 30)")
    args = parser.parse_args()
    
    gc(dry_run=not args.no_dry_run, ttl_days=args.ttl)
