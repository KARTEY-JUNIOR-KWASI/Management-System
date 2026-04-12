from django.db.models import Avg, Sum, F, Window
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Circle, String, Rect, Group
from reportlab.graphics.charts.barcharts import VerticalBarChart
from core.models import Result, SchoolConfiguration

def calculate_letter_grade(percentage):
    """Standard institutional grading scale."""
    if percentage >= 80: return 'A'
    if percentage >= 70: return 'B'
    if percentage >= 60: return 'C'
    if percentage >= 50: return 'D'
    return 'F'

def get_student_class_rank(student, academic_year=None):
    """
    Calculates the student's rank relative to their class peers.
    Uses performance aggregation across all subjects.
    """
    if not student.class_enrolled:
        return None, 0

    # Get all students in the same class
    class_peers = student.class_enrolled.student_set.all()
    
    # Calculate aggregate scores for each peer
    rankings = Result.objects.filter(
        student__class_enrolled=student.class_enrolled
    ).values('student').annotate(
        avg_score=Avg('score')
    ).order_by('-avg_score')

    # Convert to list to find index
    peer_scores = list(rankings)
    total_peers = len(peer_scores) or class_peers.count()
    
    for index, entry in enumerate(peer_scores):
        if entry['student'] == student.id:
            return index + 1, total_peers
            
    return None, total_peers

def draw_institutional_seal():
    """Generates a premium vector-based institutional seal for PDF embedding."""
    d = Drawing(100, 100)
    # Background Outer Circle - Deep Navy
    d.add(Circle(50, 50, 45, fillColor=colors.HexColor('#0F172A'), strokeColor=colors.HexColor('#4361EE'), strokeWidth=3))
    # Inner Decorative Circle - Light Border
    d.add(Circle(50, 50, 40, fillColor=None, strokeColor=colors.HexColor('#475569'), strokeWidth=1))
    # Text placeholder - Gold/White
    d.add(String(50, 48, "INSTITUTIONAL", fontName="Helvetica-Bold", fontSize=6, textAnchor="middle", fillColor=colors.white))
    d.add(String(50, 38, "CERTIFIED", fontName="Helvetica-Bold", fontSize=8, textAnchor="middle", fillColor=colors.HexColor('#F59E0B')))
    return d

def draw_performance_chart(performance_data):
    """Generates a premium bar chart for the report card with curated colors."""
    d = Drawing(400, 150)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 50
    bc.height = 80
    bc.width = 300
    
    data = [[float(p['percentage'].strip('%')) for p in performance_data]]
    bc.data = data
    bc.strokeColor = colors.HexColor('#E2E8F0')
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 100
    bc.valueAxis.valueStep = 20
    bc.valueAxis.labels.fontSize = 8
    
    bc.categoryAxis.labels.boxAnchor = 'ne'
    bc.categoryAxis.labels.dx = 8
    bc.categoryAxis.labels.dy = -2
    bc.categoryAxis.labels.angle = 30
    bc.categoryAxis.labels.fontSize = 8
    bc.categoryAxis.categoryNames = [p['subject'][:12] for p in performance_data]
    
    # Custom colored bars based on high-contrast palette
    bc.bars[0].fillColor = colors.HexColor('#4361EE') # Primary Blue
    bc.bars.strokeWidth = 0 # No borders for cleaner look
    
    d.add(bc)
    return d


def get_institutional_metadata():
    """Retrieves school config for report headers."""
    return SchoolConfiguration.get_config()
