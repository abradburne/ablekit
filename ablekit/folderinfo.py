from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Role

# Live 12 stores browser tags in XMP sidecars under this constant filename
# (verified against factory packs and the LiveTagger project).
FOLDER_INFO_DIR = 'Ableton Folder Info'
XMP_NAME = 'dc66a3fa-0fe1-5352-91cf-3ec237e9ee90.xmp'

NI_TAG = 'Creator|Native Instruments'
CREATOR_TAG = 'Creator|Ablekit'
KIT_TAGS = ['Drums|Drum Kit|Hybrid Kit', NI_TAG, CREATOR_TAG]


def expansion_tag(expansion_name: str) -> str:
    """Tag that lets Live's filter pane group browser items by expansion pack."""
    return f'Expansion|{expansion_name}'


def kit_tags(expansion_name: str) -> list[str]:
    """Kit tags plus an expansion tag so Live's filter pane can group by pack."""
    return KIT_TAGS + [expansion_tag(expansion_name)]

ROLE_TAGS: dict[Role, str] = {
    Role.KICK: 'Drums|Kick',
    Role.SNARE: 'Drums|Snare|Snare Hit',
    Role.RIM: 'Drums|Snare|Rim',
    Role.CLAP: 'Drums|Clap',
    Role.CLOSED_HH: 'Drums|Hihat|Closed Hihat',
    Role.OPEN_HH: 'Drums|Hihat|Open Hihat',
    Role.PEDAL_HH: 'Drums|Hihat|Pedal Hihat',
    Role.TOM: 'Drums|Tom',
    Role.CRASH: 'Drums|Cymbal|Crash',
    Role.RIDE: 'Drums|Cymbal|Ride',
    Role.PERC: 'Drums|Percussion',
}


def sample_tags(role: Role, expansion_name: str | None = None) -> list[str]:
    tags = []
    if role in ROLE_TAGS:
        tags.append(ROLE_TAGS[role])
    tags.append('Type|Loop' if role is Role.LOOP else 'Type|One Shot')
    tags.append(NI_TAG)
    tags.append(CREATOR_TAG)
    if expansion_name is not None:
        tags.append(expansion_tag(expansion_name))
    return tags


def _item(file_name: str, keywords: list[str]) -> str:
    lines = '\n'.join(
        f'                        <rdf:li>{escape(k)}</rdf:li>' for k in keywords)
    return f'''               <rdf:li rdf:parseType="Resource">
                  <ablFR:filePath>{escape(file_name)}</ablFR:filePath>
                  <ablFR:keywords>
                     <rdf:Bag>
{lines}
                     </rdf:Bag>
                  </ablFR:keywords>
               </rdf:li>'''


def write_folder_info(folder: Path, items: dict[str, list[str]]) -> Path:
    """Write a Live 12 tag sidecar for files in folder.

    items: file name (relative to folder) -> keyword list.
    Returns the path of the written .xmp.
    """
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    body = '\n'.join(_item(name, kw) for name, kw in sorted(items.items()))
    xmp = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 5.6.0">
   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about=""
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:ablFR="https://ns.ableton.com/xmp/fs-resources/1.0/"
            xmlns:xmp="http://ns.adobe.com/xap/1.0/">
         <dc:format>application/vnd.ableton.folder</dc:format>
         <ablFR:resource>folder</ablFR:resource>
         <ablFR:platform>mac</ablFR:platform>
         <ablFR:items>
            <rdf:Bag>
{body}
            </rdf:Bag>
         </ablFR:items>
         <xmp:CreatorTool>Ablekit</xmp:CreatorTool>
         <xmp:CreateDate>{now}</xmp:CreateDate>
         <xmp:MetadataDate>{now}</xmp:MetadataDate>
      </rdf:Description>
   </rdf:RDF>
</x:xmpmeta>
'''
    dest_dir = folder / FOLDER_INFO_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / XMP_NAME
    dest.write_text(xmp)
    return dest
