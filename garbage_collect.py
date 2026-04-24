import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from db import get_db

def gc(dry_run=True, ttl_days=30):
    conn = get_db()
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=ttl_days)
    
    report = {
        "deleted_files": [],
        "orphaned_removed": 0,
        "trash_removed": 0,
        "total_size_freed": 0
    }

    print(f"Starting Garbage Collection (Dry Run: {dry_run}, TTL: {ttl_days} days)")
    print(f"Cutoff date: {cutoff_date}")

    # 1. Identify candidates for deletion
    # - status = 'orphaned' AND created_at < cutoff AND user_touched = 0
    # - status = 'deleted' AND created_at < cutoff
    
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
            
        if not dry_run:
            try:
                if path.exists():
                    path.unlink()
                cursor.execute("DELETE FROM images WHERE id = ?", (img_id,))
                report["deleted_files"].append(path_str)
            except Exception as e:
                print(f"Error deleting {path_str}: {e}")
                continue
        else:
            report["deleted_files"].append(f"[DRY RUN] {path_str}")

        if status == 'orphaned': report["orphaned_removed"] += 1
        else: report["trash_removed"] += 1
        report["total_size_freed"] += size

    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print("\n--- GC Summary ---")
    print(f"Files removed: {len(report['deleted_files'])}")
    print(f"  - From Orphaned: {report['orphaned_removed']}")
    print(f"  - From Trash: {report['trash_removed']}")
    print(f"Total size freed: {report['total_size_freed'] / 1024 / 1024:.2f} MB")
    
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Garbage Collect orphaned/deleted images")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually delete files")
    parser.add_argument("--ttl", type=int, default=30, help="TTL in days (default 30)")
    args = parser.parse_args()
    
    gc(dry_run=not args.no_dry_run, ttl_days=args.ttl)
